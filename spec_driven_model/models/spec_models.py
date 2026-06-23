# Copyright 2019-TODAY Akretion - Raphael Valyi <raphael.valyi@akretion.com>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html).

import logging
import sys
from collections import OrderedDict
from importlib import import_module
from inspect import getmembers, isclass

from odoo import SUPERUSER_ID, _, api, models
from odoo.tools import mute_logger

_logger = logging.getLogger(__name__)


def _get_spec_mappings(registry):
    """Get the spec mixin-to-concrete mapping dict from the registry.

    This replaces the former module-level SPEC_MIXIN_MAPPINGS global.
    Attaching mappings to the registry ensures they are properly scoped
    to each database and are rebuilt on registry reloads (e.g. during
    tests), avoiding stale state leaks.
    """
    if not hasattr(registry, "_spec_mixin_mappings"):
        registry._spec_mixin_mappings = {}
    return registry._spec_mixin_mappings


def _inject_parent(cls, registry, parent_name):
    """Dynamically inject a parent class at runtime.

    Used by SpecModel._spec_build_model to inject ``spec.mixin`` as a
    parent of ``spec.mixin.<schema>`` so that spec modules do not
    need a hard dependency on spec_driven_model.  Idempotent: if
    the parent is already present this is a no-op.

    In Odoo 19, ``add_to_registry`` already merged model classes into
    ``_base_classes__``; we update both ``_base_classes__`` and
    ``__bases__`` so that ``_prepare_setup`` picks up the new parent.
    """
    existing_bases = getattr(cls, "_base_classes__", None) or cls.__bases__
    existing_names = {
        getattr(c, "_name", getattr(c, "__name__", None)) for c in existing_bases
    }
    if parent_name in existing_names:
        return  # already injected

    parent_cls = registry[parent_name]

    # Update _inherit so the framework knows about the relationship
    current_inherit = list(cls._inherit)
    if parent_name not in current_inherit:
        current_inherit.append(parent_name)
    cls._inherit = current_inherit

    # Update _base_classes__ so _prepare_setup will set __bases__ correctly
    cls._base_classes__ = (parent_cls,) + tuple(existing_bases)
    # Also set __bases__ immediately (for cases where _prepare_setup already ran)
    if parent_cls not in cls.__bases__:
        cls.__bases__ = (parent_cls,) + cls.__bases__

    # Mark for re-setup
    cls._setup_done__ = False


class SelectionMuteLogger(mute_logger):
    """
    The following fields.Selection warnings seem both very hard to
    avoid and benign in the spec_driven_model framework context.
    All in all, muting these 2 warnings seems like the best option.
    """

    def filter(self, record):
        msg = record.getMessage()
        if (
            "selection attribute will be ignored" in msg
            or "overrides existing selection" in msg
        ):
            return 0
        return super().filter(record)


class SpecModel(models.Model):
    """When you inherit this Model, then your model becomes concrete just like
    models.Model and it can use _inherit to inherit from several xsd generated
    spec mixins.
    All your model relational fields will be automatically mutated according to
    which concrete models the spec mixins where injected in.
    Because of this field mutation logic in _build_model, SpecModel should be
    inherited the Python way YourModel(spec_models.SpecModel)
    and not through _inherit.
    """

    _inherit = ["spec.mixin"]
    _auto = True  # automatically create database backend
    _register = False  # not visible in ORM registry
    _abstract = False
    _transient = False

    # TODO generic onchange method that check spec field simple type formats
    # xsd_required, according to the considered object context
    # and return warning or reformat things
    # ideally the list of onchange fields is set dynamically but if it is too
    # hard, we can just dump the list of fields when SpecModel is loaded

    # TODO a save python constraint that ensuire xsd_required fields for the
    # context are present

    @api.depends(lambda self: (self._rec_name,) if self._rec_name else ())
    def _compute_display_name(self):
        "More user friendly when automatic _rec_name is bad"
        res = super()._compute_display_name()
        for rec in self:
            if rec.display_name == "False" or not rec.display_name:
                rec.display_name = _("Open...")
        return res

    @classmethod
    def _spec_build_model(cls, registry, cr=None):
        """
        Odoo 19 replacement for the old _build_model classmethod.

        In Odoo 18, _build_model was called by the framework. In Odoo 19,
        _build_model was removed from the ORM (the lifecycle is now
        add_to_registry → _setup_models__ → setup_model_classes).
        This method must be called manually for spec models after
        add_to_registry but before _setup_models__.

        It does two things:
        1. Inject spec.mixin as parent of spec.mixin.<schema> (loose coupling)
        2. Register concrete model mappings (_map_concrete)
        """
        with mute_logger("odoo.tests.common"):
            # Discover schema from class-level spec_schema on MRO ancestors
            schema = None
            for kls in cls.mro():
                schema = getattr(kls, "spec_schema", None)
                if schema:
                    break
            # Fallback to module-level spec_schema
            if not schema:
                try:
                    mod = import_module(".".join(cls.__module__.split(".")[:-1]))
                    schema = getattr(mod, "spec_schema", None)
                except Exception:
                    pass

            if schema and f"spec.mixin.{schema}" in registry:
                _inject_parent(
                    registry[f"spec.mixin.{schema}"], registry, "spec.mixin"
                )

            parents = [
                item[0] if isinstance(item, list) else item
                for item in list(cls._inherit)
            ]
            for parent in parents:
                if parent == cls._name:
                    continue
                # this will register that the spec mixins were injected in this class
                cls._map_concrete(registry, parent, cls._name)

    def _post_model_setup__(self):
        """
        Odoo 19 hook that replaces the old _setup_fields override.
        Called after all fields are collected and set up.

        Here we do the comodel remapping: spec mixin fields that point
        to abstract spec models get their comodel_name remapped to the
        concrete Odoo models where those mixins were injected.
        """
        res = super()._post_model_setup__()
        self._spec_remap_comodels()
        return res

    def _spec_remap_comodels(self):
        """Remap relational field comodels from abstract spec models to
        concrete Odoo models, and clean up stacking fields.

        In Odoo 18 this was done in _setup_fields BEFORE field.setup().
        In Odoo 19, _setup_fields is a module function. We do the remapping
        here, then trigger a re-setup of the affected fields.
        """
        cls = type(self)
        registry = self.env.registry
        mappings = _get_spec_mappings(registry)

        # Clean up stacking many2one fields: they shouldn't be direct
        # model fields (StackedModel._add_field skipped them in Odoo 18,
        # but the module-level setup in Odoo 19 adds them anyway).
        sp = self._get_stacking_points()
        if sp:
            # Remove stacking field entries from _fields__
            cls._fields__ = {
                k: v for k, v in cls._fields__.items()
                if not (k in sp and v.type == "many2one")
            }

        # First: map concrete for all spec-driven parents
        for klass in cls.__bases__:
            if not hasattr(klass, "_is_spec_driven"):
                continue
            if klass._name != cls._name:
                cls._map_concrete(registry, klass._name, cls._name)
                with mute_logger("odoo.tests.common"):
                    klass._table = cls._table

        stacked_parents = [getattr(x, "_name", None) for x in cls.mro()]
        remapped = False
        for name, field in cls._fields.items():
            if not hasattr(field, "comodel_name") or not field.comodel_name:
                continue

            comodel_name = field.comodel_name
            concrete_class = mappings.get(comodel_name)

            if (
                field.type == "many2one"
                and concrete_class is not None
                and concrete_class != comodel_name
                and comodel_name not in stacked_parents
            ):
                _logger.debug(
                    "    MUTATING m2o %s (%s) -> %s",
                    name, comodel_name, concrete_class,
                )
                if not hasattr(field, "original_comodel_name"):
                    field.original_comodel_name = comodel_name
                field.comodel_name = concrete_class
                field._setup_done = False
                remapped = True

            elif field.type == "one2many" and concrete_class is not None:
                _logger.debug(
                    "    MUTATING o2m %s (%s) -> %s",
                    name, comodel_name, concrete_class,
                )
                if not hasattr(field, "original_comodel_name"):
                    field.original_comodel_name = comodel_name
                field.comodel_name = concrete_class
                field._setup_done = False
                remapped = True

        if remapped:
            # Re-setup the fields that were modified
            model = cls(self.env, (), ())
            for name, field in cls._fields.items():
                if not field._setup_done:
                    field.setup(model)

    @classmethod
    def _map_concrete(cls, registry, key, target, quiet=False):
        _logger.info("_map_concrete: %s -> %s (quiet=%s)", key, target, quiet)
        mappings = _get_spec_mappings(registry)
        _logger.info("  registry id=%s, mappings id=%s, current=%s", id(registry), id(mappings), dict(mappings))
        mappings[key] = target

    @classmethod
    def spec_module_classes(cls, spec_module):
        """
        Cache the list of spec_module classes to save calls to
        slow reflection API.
        """
        spec_module_attr = f"_spec_cache_{spec_module.replace('.', '_')}"
        if not hasattr(cls, spec_module_attr):
            with mute_logger("odoo.tests.common"):
                setattr(
                    cls,
                    spec_module_attr,
                    getmembers(sys.modules[spec_module], isclass),
                )
        return getattr(cls, spec_module_attr)

    @classmethod
    def _odoo_name_to_class(cls, odoo_name, spec_module):
        for _name, base_class in cls.spec_module_classes(spec_module):
            if base_class._name == odoo_name:
                return base_class
        return None


class StackedModel(SpecModel):
    """
    XML structures are typically deeply nested as this helps xsd
    validation. However, deeply nested objects in Odoo suck because that would
    mean crazy joins accross many tables and also an endless cascade of form
    popups.

    By inheriting from StackModel instead, your models.Model can
    instead inherit all the mixins that would correspond to the nested xsd
    nodes starting from the stacking_mixin. stacking_skip_paths allows you to avoid
    stacking specific nodes while stacking_force_paths will stack many2one
    entities even if they are not required.

    In Brazil it allows us to have mostly the fiscal
    document objects and the fiscal document line object with many details
    stacked in a denormalized way inside these two tables only.
    """

    _register = False  # forces you to inherit StackeModel properly

    @classmethod
    def _spec_build_model(cls, registry, cr=None):
        """
        Odoo 19 replacement for the old _build_model classmethod.
        Sets up stacking points and injects stacked mixins.
        """
        with mute_logger("odoo.tests.common"):
            # Discover schema/version from class-level attributes on MRO ancestors
            schema = None
            version = None
            for kls in cls.mro():
                schema = getattr(kls, "spec_schema", None)
                version = getattr(kls, "spec_version", None)
                if schema and version:
                    break
            # Fallback to module-level attributes
            if not schema or not version:
                try:
                    mod = import_module(".".join(cls.__module__.split(".")[:-1]))
                    if not schema:
                        schema = getattr(mod, "spec_schema", None)
                    if not version:
                        version = getattr(mod, "spec_version", None)
                except Exception:
                    pass
            if version:
                version = version.replace(".", "")[:2]
            spec_prefix = f"{schema}{version}"
            setattr(cls, f"_{spec_prefix}_stacking_points", {})

        stacking_settings = {
            "odoo_module": getattr(cls, f"_{spec_prefix}_odoo_module"),
            "stacking_mixin": getattr(cls, f"_{spec_prefix}_stacking_mixin"),
            "stacking_points": getattr(cls, f"_{spec_prefix}_stacking_points"),
            "stacking_skip_paths": getattr(
                cls, f"_{spec_prefix}_stacking_skip_paths", []
            ),
            "stacking_force_paths": getattr(
                cls, f"_{spec_prefix}_stacking_force_paths", []
            ),
        }
        # inject all stacked m2o as inherited classes
        _logger.info(f"building StackedModel {cls._name} {cls}")
        node = cls._odoo_name_to_class(
            stacking_settings["stacking_mixin"], stacking_settings["odoo_module"]
        )
        env = api.Environment(cr, SUPERUSER_ID, {}) if cr else None
        for kind, klass, _path, _field_path, _child_concrete in cls._visit_stack(
            env, node, stacking_settings
        ):
            if kind == "stacked" and klass not in cls.__bases__:
                # Add to _inherit and _base_classes__ for Odoo 19
                if klass._name not in cls._inherit:
                    cls._inherit.append(klass._name)
                # Ensure the stacked class is in _base_classes__
                current_bases = list(getattr(cls, "_base_classes__", cls.__bases__))
                if klass not in current_bases:
                    current_bases.append(klass)
                    cls._base_classes__ = tuple(current_bases)

        # Also do the SpecModel-level injection (spec.mixin parent, _map_concrete)
        super()._spec_build_model(registry, cr)

        # Mark for re-setup
        cls._setup_done__ = False

    @api.model
    def _add_field(self, name, field):
        """
        Overriden to avoid adding many2one fields that are in fact "stacking points"
        """
        if field.type == "many2one":
            for cls in type(self).mro():
                if issubclass(cls, StackedModel):
                    for attr in dir(cls):
                        if attr != "_get_stacking_points" and attr.endswith(
                            "_stacking_points"
                        ):
                            if name in getattr(cls, attr).keys():
                                return
        return super()._add_field(name, field)

    @classmethod
    def _visit_stack(cls, env, node, stacking_settings, path=None):
        """Pre-order traversal of the stacked models tree.
        1. This method is used to dynamically inherit all the spec models
        stacked together from an XML hierarchy.
        2. It is also useful to generate an automatic view of the spec fields.
        3. Finally it is used when exporting as XML.
        """
        if path is None:
            path = stacking_settings["stacking_mixin"].split(".")[-1]
        cls._map_concrete(env.registry, node._name, cls._name, quiet=True)
        yield "stacked", node, path, None, None

        # Collect fields from the node model.
        # In Odoo 19, abstract models may not have been set up yet.
        # We read field definitions directly from the model definition classes.
        fields = OrderedDict()
        node_cls = env.registry.get(node._name) if env else None
        field_items = []
        if node_cls:
            # Try to get fields from the registry class
            if hasattr(node_cls, "_fields") and len(node_cls._fields) > 0:
                field_items = list(node_cls._fields.items())
            else:
                # Collect from model definition classes directly
                for def_cls in reversed(node_cls.mro()):
                    if hasattr(def_cls, "_field_definitions"):
                        for f in def_cls._field_definitions:
                            field_items.append((f.name, f))

        for i in field_items:
            f = i[1]
            fields[i[0]] = {
                "type": f.type,
                "comodel_name": getattr(f, "comodel_name", None),
                "xsd_required": hasattr(f, "xsd_required") and f.xsd_required,
                "xsd_choice_required": hasattr(f, "xsd_choice_required")
                and f.xsd_choice_required,
            }
        for name, f in fields.items():
            if f["type"] not in [
                "many2one",
                "one2many",
            ] or name in stacking_settings.get("stacking_skip_paths", ""):
                continue
            child = cls._odoo_name_to_class(
                f["comodel_name"], stacking_settings["odoo_module"]
            )
            if child is None:  # Not a spec field
                continue
            child_concrete = _get_spec_mappings(env.registry).get(child._name)
            field_path = name.split("_")[1]  # remove schema prefix

            if f["type"] == "one2many":
                yield "one2many", node, path, field_path, child_concrete
                continue

            force_stacked = any(
                stack_path in path + "." + field_path
                for stack_path in stacking_settings.get("stacking_force_paths", [])
            )

            _logger.info(
                "_visit_stack field=%s comodel=%s child_concrete=%s cls._name=%s xsd_req=%s force=%s",
                name, f["comodel_name"], child_concrete, cls._name,
                f.get("xsd_required"), force_stacked
            )

            # many2one
            if (child_concrete is None or child_concrete == cls._name) and (
                f["xsd_required"] or f["xsd_choice_required"] or force_stacked
            ):
                # then we will STACK the child in the current class
                _logger.info("STACKING %s (%s) child_concrete=%s cls._name=%s", name, child._name, child_concrete, cls._name)
                with mute_logger("odoo.tests.common"):
                    child._stack_path = path
                child_path = f"{path}.{field_path}"
                # Get the field from the node's definition or registry
                stored_field = None
                if env and node._name in env.registry:
                    stored_field = env[node._name]._fields.get(name)
                stacking_settings["stacking_points"][name] = stored_field or name
                yield from cls._visit_stack(env, child, stacking_settings, child_path)
            else:
                yield "many2one", node, path, field_path, child_concrete
