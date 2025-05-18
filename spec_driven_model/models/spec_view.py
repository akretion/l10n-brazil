# spec_driven_model/models/spec_view.py
import logging
from lxml import etree
from lxml.builder import E

from odoo import api, models, _

_logger = logging.getLogger(__name__)


def get_concrete_model_name(env, abstract_model_name):
    from .spec_models import SPEC_MIXIN_MAPPINGS  # Local import for safety

    if not abstract_model_name:  # Should not happen if field def is correct
        return None
    return SPEC_MIXIN_MAPPINGS[env.cr.dbname].get(
        abstract_model_name, abstract_model_name
    )


class SpecViewMixin(models.AbstractModel):
    _name = "spec.mixin.view"
    _description = "Automatic View Generation for Spec-Driven Models"

    # --- Configuration Hooks (to be overridden by concrete models) ---

    def _get_spec_view_page_title(self, spec_prefix):
        """Return the title for the spec tab/page/group."""
        return f"{spec_prefix.upper()} Details"

    def _get_spec_view_field_settings(self, spec_prefix):
        """
        Return a dictionary for field-specific view customizations.
        Example:
        {
            'my_prefix_field_name': {'widget': 'many2many_tags', 'attrs': "{'invisible': [('state', '=', 'done')]}"},
            'my_prefix_other_field': {'invisible': "1"} # Static invisibility
        }
        """
        return getattr(self, f"_{spec_prefix}_view_field_settings", {})

    def _get_spec_view_custom_xml_override(self, spec_prefix, path_str):
        """
        Return custom XML (string) to replace auto-generated
        part for a given path_str (e.g., 'parent_group.child_group' or 'parent.field_representing_group').
        Return None to use auto-generation.
        """
        # _logger.debug(f"SPEC_VIEW_OVERRIDE_CHECK: Model {self._name}, Prefix {spec_prefix}, Path {path_str}")
        return None  # Default: no override

    # --- Main View Generation Logic ---

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        res = super().get_view(view_id=view_id, view_type=view_type, **options)

        # Guard against recursive calls and non-form views
        if self._context.get("spec_view_processed") or view_type != "form":
            return res

        current_spec_prefix = self._context.get("spec_prefix")
        if not current_spec_prefix and hasattr(self, "_spec_prefix"):
            current_spec_prefix = self._spec_prefix()

        if not current_spec_prefix:
            return res  # No specific spec context to generate for

        # Check if this model is relevant for spec view generation
        schema_part = current_spec_prefix.rstrip("0123456789")
        is_stacked = hasattr(self, f"_{current_spec_prefix}_stacking_mixin")
        has_spec_mixin_in_inherit = any(
            isinstance(base_name, str) and base_name.startswith(f"{schema_part}.")
            for base_name in getattr(self, "_inherit", [])
        )
        is_direct_spec_model = self._name.startswith(f"{schema_part}.")

        if (
            not is_stacked
            and not has_spec_mixin_in_inherit
            and not is_direct_spec_model
        ):
            return res  # Not a spec-driven model we can auto-generate views for easily

        _logger.debug(
            f"SPEC_VIEW_GET_VIEW: Processing {self._name}, type {view_type}, prefix {current_spec_prefix}"
        )

        doc = etree.fromstring(res["arch"])
        generated_fields = set()
        view_name_from_res = res.get("name", "default")

        injection_point = None
        injection_mode = "page"

        if doc.xpath("//notebook"):
            injection_point = doc.xpath("//notebook")[0]
            injection_mode = "page"
        elif doc.xpath("//sheet"):
            injection_point = doc.xpath("//sheet")[0]
            is_default_view = (
                "default" in str(view_id or "") or "default" in view_name_from_res
            )
            if is_default_view and is_direct_spec_model:
                injection_mode = "replace_sheet_content"
            else:
                injection_mode = "group"
        elif doc.xpath("//form"):  # Typically for lines or simple views
            injection_point = doc.xpath("//form")[0]
            injection_mode = "append_to_form"

        if (
            injection_point is None and is_direct_spec_model
        ):  # Likely an auto-generated model by _register_hook
            doc = E.form()
            # Set form title for auto-generated views
            doc.set("string", self._description or self._name)
            sheet = E.sheet()
            doc.append(sheet)
            injection_point = sheet  # Inject into this new sheet
            injection_mode = "replace_sheet_content"

        if injection_point is not None:
            spec_arch_fragment, new_fields = self._build_spec_view_fragment(
                current_spec_prefix
            )
            generated_fields.update(new_fields)

            if spec_arch_fragment is not None and list(
                spec_arch_fragment
            ):  # Check if fragment has content
                page_or_group_title = self._get_spec_view_page_title(
                    current_spec_prefix
                )
                _logger.debug(
                    f"SPEC_VIEW_GET_VIEW: Injecting fragment titled '{page_or_group_title}', mode '{injection_mode}' into {injection_point.tag}"
                )

                if injection_mode == "page":
                    page = E.page(string=page_or_group_title)
                    for child in list(spec_arch_fragment):
                        page.append(child)
                    injection_point.append(page)
                elif injection_mode == "group":
                    # The fragment is typically a group. Set its title and properties.
                    if spec_arch_fragment.tag == "group":
                        spec_arch_fragment.set("string", page_or_group_title)
                        if not spec_arch_fragment.get("col"):
                            spec_arch_fragment.set("col", "4")
                        if not spec_arch_fragment.get("colspan"):
                            spec_arch_fragment.set("colspan", "4")
                        injection_point.append(spec_arch_fragment)
                    else:  # Should not happen if _build_spec_view_fragment returns a group
                        outer_group = E.group(
                            string=page_or_group_title, col="4", colspan="4"
                        )
                        for child in list(spec_arch_fragment):
                            outer_group.append(child)
                        injection_point.append(outer_group)
                elif injection_mode == "replace_sheet_content":
                    for child_node in list(injection_point):
                        injection_point.remove(child_node)
                    if spec_arch_fragment.tag == "group":
                        spec_arch_fragment.set(
                            "col", "4"
                        )  # Standard layout for main content
                        spec_arch_fragment.set(
                            "string", page_or_group_title
                        )  # Use specific title
                    # Ensure sheet itself gets a title if it doesn't have one
                    if not injection_point.get("string"):
                        injection_point.set("string", self._description or self._name)
                    injection_point.append(spec_arch_fragment)
                elif (
                    injection_mode == "append_to_form"
                ):  # Append children of fragment to form
                    for child_node in list(spec_arch_fragment):
                        injection_point.append(child_node)
            else:
                _logger.debug(
                    f"SPEC_VIEW_GET_VIEW: No spec_arch_fragment generated or fragment is empty for {self._name}, prefix {current_spec_prefix}"
                )

        res_fields = res.get("fields", {})
        # Get field info for all fields that might have been generated
        # Filter out sub-fields (like 'o2m_field.line_field_name') before calling fields_get
        top_level_generated_fields = {f.split(".")[0] for f in generated_fields}
        current_fields_info = self.fields_get(
            allfields=list(top_level_generated_fields)
        )

        for field_name in top_level_generated_fields:
            if field_name not in res_fields and field_name in current_fields_info:
                field_info = current_fields_info[field_name]
                if field_info.get("type") in ["one2many", "many2one"]:
                    field_info["views"] = (
                        {}
                    )  # Default: no inline views for generated relational fields
                res_fields[field_name] = field_info
        res["fields"] = res_fields

        res["arch"] = etree.tostring(doc, encoding="unicode")
        return res

    @api.model
    def _build_spec_view_fragment(self, spec_prefix):
        generated_fields = set()
        # The root_container will be the main group for this spec's fields
        root_container = E.group()

        if hasattr(self, f"_{spec_prefix}_stacking_mixin"):
            stacking_settings_attr = (
                f"_{spec_prefix}_spec_settings"  # General convention
            )
            stacking_settings_val = getattr(self, stacking_settings_attr, None)
            if not stacking_settings_val:  # Fallback to older individual attributes
                stacking_settings_val = {
                    "odoo_module": getattr(self, f"_{spec_prefix}_odoo_module", None),
                    "stacking_mixin": getattr(
                        self, f"_{spec_prefix}_stacking_mixin", None
                    ),
                    "stacking_points": getattr(
                        self, f"_{spec_prefix}_stacking_points", {}
                    ),
                    "stacking_skip_paths": getattr(
                        self, f"_{spec_prefix}_stacking_skip_paths", []
                    ),
                    "stacking_force_paths": getattr(
                        self, f"_{spec_prefix}_stacking_force_paths", []
                    ),
                }

            if (
                not stacking_settings_val
                or not stacking_settings_val.get("stacking_mixin")
                or not stacking_settings_val.get("odoo_module")
            ):
                _logger.error(
                    f"StackedModel {self._name} misconfigured for spec_prefix {spec_prefix}. Missing stacking_mixin or odoo_module for spec settings."
                )
                return None, generated_fields

            start_node_abstract_name = stacking_settings_val["stacking_mixin"]
            start_node_cls = self.env[start_node_abstract_name]
            # Path prefix for the root of the stacked structure
            path_prefix_start = start_node_abstract_name.split(".")[-1]

            self._recursive_build_view_arch(
                spec_prefix,
                self,
                start_node_cls,
                root_container,
                generated_fields,
                stacking_settings_val,
                path_prefix_start,
                depth=0,
            )
        else:  # Not a StackedModel, or no stacking_mixin defined for this prefix
            schema_part = spec_prefix.rstrip("0123456789")
            spec_model_name_to_build = None
            if self._name.startswith(f"{schema_part}."):  # Is it a direct spec model?
                spec_model_name_to_build = self._name
            else:  # Is it injected into another model?
                for base_name in getattr(self, "_inherit", []):
                    if isinstance(base_name, str) and base_name.startswith(
                        f"{schema_part}."
                    ):
                        spec_model_name_to_build = base_name
                        break

            if spec_model_name_to_build:
                start_node_cls = self.env[spec_model_name_to_build]
                path_prefix_start = spec_model_name_to_build.split(".")[-1]
                self._recursive_build_view_arch(
                    spec_prefix,
                    self,
                    start_node_cls,
                    root_container,
                    generated_fields,
                    None,
                    path_prefix_start,
                    depth=0,  # No stacking_settings for this path
                )
            else:
                _logger.warning(
                    f"Could not determine starting spec node for {self._name} and prefix {spec_prefix} in _build_spec_view_fragment."
                )
                return None, generated_fields

        if not list(
            root_container
        ):  # Check if any actual content (fields, groups) was added
            _logger.debug(
                f"SpecViewMixin: Root container for fragment is empty for {self._name}, prefix {spec_prefix}."
            )
            return None, generated_fields
        return root_container, generated_fields

    @api.model
    def _recursive_build_view_arch(
        self,
        spec_prefix,
        concrete_model_cls,
        current_spec_node_cls,
        view_parent_node,
        generated_fields,
        stacking_settings,
        path_prefix,
        depth,  # path_prefix is like 'purchaseordertype' or 'purchaseordertype.items'
    ):
        _logger.debug(
            f"RECURSIVE_VIEW_BUILD: concrete={concrete_model_cls._name}, spec_node={current_spec_node_cls._name}, path_prefix={path_prefix}, depth={depth}"
        )
        field_settings_for_prefix = concrete_model_cls._get_spec_view_field_settings(
            spec_prefix
        )

        # Check for custom XML override for the entire current path_prefix (logical group)
        custom_xml_str_for_group_path = (
            concrete_model_cls._get_spec_view_custom_xml_override(
                spec_prefix, path_prefix
            )
        )
        if custom_xml_str_for_group_path:
            _logger.info(
                f"OVERRIDE_GROUP_PATH: Applying custom XML for group path: {path_prefix} in {concrete_model_cls._name}"
            )
            try:
                custom_group_node = etree.fromstring(custom_xml_str_for_group_path)
                for f_node in custom_group_node.xpath(
                    ".//field"
                ):  # Get all descendant fields from override
                    if f_node.get("name"):
                        generated_fields.add(f_node.get("name"))

                # Append the custom node (which should be a group or similar container)
                view_parent_node.append(custom_group_node)
                return  # Entire content for this path_prefix is handled by custom XML
            except etree.XMLSyntaxError as e:
                _logger.error(
                    f"OVERRIDE_GROUP_PATH: Error parsing XML for path {path_prefix} in {concrete_model_cls._name}: {e}. Falling back."
                )

        # Ensure abstract model fields are available
        if (
            not current_spec_node_cls._fields
            and current_spec_node_cls._name != concrete_model_cls._name
        ):
            try:
                abstract_model_in_registry = self.env.registry.models.get(
                    current_spec_node_cls._name
                )
                if (
                    abstract_model_in_registry
                    and not abstract_model_in_registry._fields_setup
                ):
                    current_spec_node_cls._setup_fields()
            except Exception as e:
                _logger.error(
                    f"Failed to ensure fields setup for {current_spec_node_cls._name} during view gen: {e}"
                )

        fields_on_current_line = 0
        MAX_FIELDS_PER_LINE = 2
        field_items = list(current_spec_node_cls._fields.items())

        for idx, (field_name_on_spec_node, field_obj_on_spec_node) in enumerate(
            field_items
        ):
            if (
                not field_name_on_spec_node.startswith(spec_prefix + "_")
                or f"{spec_prefix}_choice" in field_name_on_spec_node
            ):  # Skip choice selectors
                continue

            actual_field_name_on_concrete = field_name_on_spec_node
            field_obj_on_concrete = concrete_model_cls._fields.get(
                actual_field_name_on_concrete
            )

            if not field_obj_on_concrete:
                _logger.debug(
                    f"Field {actual_field_name_on_concrete} (from spec {current_spec_node_cls._name}) not on concrete model {concrete_model_cls._name}. Skipping."
                )
                continue

            clean_field_name_for_path = actual_field_name_on_concrete[
                len(spec_prefix) + 1 :
            ]  # e.g. "items" from "poxsd10_items"
            current_field_path = f"{path_prefix}.{clean_field_name_for_path}"  # e.g. "purchaseordertype.items"
            field_view_config = field_settings_for_prefix.get(
                actual_field_name_on_concrete, {}
            )

            original_comodel_name_on_spec = field_obj_on_spec_node.comodel_name
            actual_comodel_name_on_concrete = (
                get_concrete_model_name(self.env, original_comodel_name_on_spec)
                if original_comodel_name_on_spec
                else None
            )

            # Check for custom XML override for THIS SPECIFIC FIELD's representation (current_field_path)
            custom_field_render_xml_str = (
                concrete_model_cls._get_spec_view_custom_xml_override(
                    spec_prefix, current_field_path
                )
            )
            if custom_field_render_xml_str:
                _logger.info(
                    f"OVERRIDE_FIELD_RENDER: Applying custom XML for field path: {current_field_path}"
                )
                try:
                    custom_field_node = etree.fromstring(custom_field_render_xml_str)
                    for f_node_in_custom in custom_field_node.xpath(
                        ".//field"
                    ):  # Add fields from custom node
                        if f_node_in_custom.get("name"):
                            generated_fields.add(f_node_in_custom.get("name"))
                    view_parent_node.append(
                        custom_field_node
                    )  # Append the custom rendering for this field
                    fields_on_current_line = (
                        0  # Assume custom XML handles its own layout
                    )
                    continue  # Processed this field with custom XML, move to next
                except etree.XMLSyntaxError as e:
                    _logger.error(
                        f"OVERRIDE_FIELD_RENDER: Error parsing XML for {current_field_path}: {e}. Falling back."
                    )

            is_field_stacked_by_config = False
            if stacking_settings and field_name_on_spec_node in stacking_settings.get(
                "stacking_points", {}
            ):
                if (
                    field_obj_on_spec_node.type == "many2one"
                    and original_comodel_name_on_spec
                ):
                    is_field_stacked_by_config = True
                else:
                    _logger.warning(
                        f"Field {field_name_on_spec_node} configured as stacking point but not M2O/no comodel in spec for {current_spec_node_cls._name}."
                    )

            if is_field_stacked_by_config:
                _logger.info(
                    f"STACKED_FIELD_CONTENT: Processing '{field_name_on_spec_node}' (path: {current_field_path}) as stacked content for {concrete_model_cls._name}"
                )
                if fields_on_current_line > 0:
                    view_parent_node.append(E.newline())
                    fields_on_current_line = 0

                group_label = (
                    field_obj_on_concrete.string
                    or clean_field_name_for_path.capitalize()
                )
                inner_group_for_stack = E.group(string=group_label, colspan="4")
                self._apply_common_field_attrs(
                    inner_group_for_stack, field_view_config, None
                )  # Apply config to group itself
                view_parent_node.append(inner_group_for_stack)

                stacked_abstract_spec_model_cls = self.env[
                    original_comodel_name_on_spec
                ]
                self._recursive_build_view_arch(
                    spec_prefix,
                    concrete_model_cls,
                    stacked_abstract_spec_model_cls,
                    inner_group_for_stack,
                    generated_fields,
                    stacking_settings,
                    current_field_path,  # This path (e.g. purchaseordertype.items) is now the path_prefix for the content
                    depth + 1,
                )
                fields_on_current_line = 0
                continue

            # Default rendering for fields if not overridden or stacked
            if (
                field_obj_on_concrete.type == "one2many"
                and actual_comodel_name_on_concrete
            ):
                _logger.debug(
                    f"O2M_FIELD: Rendering '{actual_field_name_on_concrete}'. Path: {current_field_path}"
                )
                if fields_on_current_line > 0:
                    view_parent_node.append(E.newline())
                    fields_on_current_line = 0
                generated_fields.add(actual_field_name_on_concrete)
                nolabel_val = field_view_config.get("nolabel", "0")
                o2m_field_node = E.field(
                    name=actual_field_name_on_concrete, nolabel=nolabel_val, colspan="4"
                )
                o2m_line_model = self.env[actual_comodel_name_on_concrete]
                o2m_tree = E.tree()
                o2m_line_form_arch_str = o2m_line_model.with_context(
                    spec_prefix=spec_prefix, spec_view_processed=True
                )._build_default_spec_form_arch(
                    spec_prefix
                )  # Prevent recursion
                o2m_line_form_node = etree.fromstring(o2m_line_form_arch_str)
                line_field_count_tree = 0
                MAX_O2M_TREE_FIELDS = 4
                if (
                    o2m_line_model._rec_name
                    and o2m_line_model._rec_name in o2m_line_model._fields
                    and o2m_line_model._fields[o2m_line_model._rec_name].type
                    not in ["one2many", "many2many", "binary"]
                ):
                    o2m_tree.append(E.field(name=o2m_line_model._rec_name))
                    line_field_count_tree += 1
                for line_fname, line_fobj in o2m_line_model._fields.items():
                    if line_fname == o2m_line_model._rec_name:
                        continue
                    if (
                        not line_fobj.automatic
                        and line_fobj.store
                        and line_fobj.type not in ["one2many", "many2many", "binary"]
                        and not line_fname.startswith(spec_prefix + "_choice")
                    ):
                        if line_field_count_tree < MAX_O2M_TREE_FIELDS:
                            o2m_tree.append(E.field(name=line_fname))
                            line_field_count_tree += 1
                if line_field_count_tree == 0 and "id" in o2m_line_model._fields:
                    o2m_tree.append(E.field(name="id"))
                o2m_field_node.append(o2m_tree)
                o2m_field_node.append(o2m_line_form_node)
                self._apply_common_field_attrs(
                    o2m_field_node, field_view_config, field_obj_on_concrete
                )
                view_parent_node.append(o2m_field_node)
                fields_on_current_line = 0
                continue

            elif (
                field_obj_on_concrete.type == "many2one"
                and actual_comodel_name_on_concrete
            ):
                _logger.debug(
                    f"M2O_FIELD: Rendering '{actual_field_name_on_concrete}'. Path: {current_field_path}"
                )
                generated_fields.add(actual_field_name_on_concrete)
                m2o_field_node = E.field(name=actual_field_name_on_concrete)
                self._apply_common_field_attrs(
                    m2o_field_node, field_view_config, field_obj_on_concrete
                )
                view_parent_node.append(m2o_field_node)
                fields_on_current_line += 1

            elif field_obj_on_concrete.type not in [
                "binary",
                "reference",
                "serialized",
                "one2many",
                "many2many",
            ]:  # Simple fields
                _logger.debug(
                    f"SIMPLE_FIELD: Rendering '{actual_field_name_on_concrete}'. Path: {current_field_path}"
                )
                generated_fields.add(actual_field_name_on_concrete)
                simple_field_node = E.field(name=actual_field_name_on_concrete)
                if field_obj_on_concrete.type in (
                    "text",
                    "html",
                ) and not field_view_config.get("colspan"):
                    simple_field_node.set("colspan", "4")
                self._apply_common_field_attrs(
                    simple_field_node, field_view_config, field_obj_on_concrete
                )
                view_parent_node.append(simple_field_node)
                fields_on_current_line += 1

            is_last_field_in_node = idx == len(field_items) - 1
            if (
                fields_on_current_line >= MAX_FIELDS_PER_LINE
                and not is_last_field_in_node
            ):
                view_parent_node.append(E.newline())
                fields_on_current_line = 0

    def _apply_common_field_attrs(self, lxml_node, field_view_config, field_obj):
        attrs_dict = {}
        try:
            existing_attrs_str = lxml_node.get("attrs")
            if existing_attrs_str:
                attrs_dict = eval(existing_attrs_str)
        except Exception:
            attrs_dict = {}

        for static_attr_name in [
            "widget",
            "options",
            "placeholder",
            "nolabel",
            "colspan",
            "string",
            "help",
            "sum",
            "avg",
        ]:
            if static_attr_name in field_view_config:
                lxml_node.set(
                    static_attr_name, str(field_view_config[static_attr_name])
                )

        for bool_attr_name in ["invisible", "readonly", "required"]:
            if bool_attr_name in field_view_config:
                val = field_view_config[bool_attr_name]
                if val == "1" or val is True:
                    lxml_node.set(bool_attr_name, "1")
                elif isinstance(val, str) and (
                    val.startswith("[") or val.startswith("(")
                ):
                    try:
                        attrs_dict[bool_attr_name] = eval(val)
                    except Exception as e:
                        _logger.error(
                            f"Failed to eval {bool_attr_name} string '{val}' for {lxml_node.get('name')}: {e}"
                        )

        if "attrs" in field_view_config:
            try:
                config_attrs = eval(field_view_config["attrs"])
                if isinstance(config_attrs, dict):
                    for key, value in config_attrs.items():
                        attrs_dict[key] = value
            except Exception as e:
                _logger.error(
                    f"Failed to eval 'attrs' string '{field_view_config['attrs']}' for {lxml_node.get('name')}: {e}"
                )

        if attrs_dict:
            final_attrs_dict = {}
            for k, v_attr in attrs_dict.items():
                if v_attr is True or v_attr == "1":
                    final_attrs_dict[k] = [("1", "=", "1")]
                elif v_attr is False or v_attr == "0":
                    final_attrs_dict[k] = [("1", "=", "0")]
                else:
                    final_attrs_dict[k] = v_attr
            if final_attrs_dict:
                lxml_node.set("attrs", str(final_attrs_dict))

        if (
            field_obj
            and field_obj.required
            and not lxml_node.get("required")
            and "required" not in attrs_dict
        ):
            if not field_view_config.get("required") in ("0", False):
                lxml_node.set("required", "1")

    @api.model
    def _get_default_spec_tree_view_arch(self, spec_prefix):
        tree = E.tree()
        count = 0
        added_fields = set()
        MAX_TREE_FIELDS = 7

        concrete_rec_name = self._rec_name
        if (
            concrete_rec_name
            and concrete_rec_name in self._fields
            and concrete_rec_name.startswith(spec_prefix + "_")
            and concrete_rec_name not in added_fields
        ):
            tree.append(E.field(name=concrete_rec_name))
            added_fields.add(concrete_rec_name)
            count += 1

        for fname, field in self._fields.items():
            if count >= MAX_TREE_FIELDS:
                break
            if fname == concrete_rec_name:
                continue

            if (
                fname.startswith(spec_prefix + "_")
                and not field.automatic
                and field.store
                and field.type
                not in ["one2many", "many2many", "binary", "html", "text"]
                and fname not in added_fields
                and not fname.startswith(spec_prefix + "_choice")
            ):
                tree.append(E.field(name=fname))
                added_fields.add(fname)
                count += 1

        if count == 0:
            if concrete_rec_name and concrete_rec_name in self._fields:
                tree.append(E.field(name=concrete_rec_name))
            elif "name" in self._fields:
                tree.append(E.field(name="name"))
            elif "id" in self._fields:
                tree.append(E.field(name="id"))
            else:
                _logger.warning(
                    f"Could not determine any field for default tree view of {self._name}"
                )
        return etree.tostring(tree, encoding="unicode")

    @classmethod
    def _create_default_spec_views(cls, env, module_name):
        if not hasattr(cls, "_spec_prefix"):
            _logger.warning(
                f"Model {cls._name} lacks _spec_prefix method, cannot auto-create default views."
            )
            return

        try:
            model_instance = env[cls._name]
        except KeyError:
            _logger.error(
                f"Model {cls._name} not found in registry during _create_default_spec_views. Skipping."
            )
            return

        spec_prefix_val = model_instance._spec_prefix()
        if not spec_prefix_val:
            _logger.warning(
                f"Cannot determine spec_prefix for {cls._name}, skipping default view creation."
            )
            return

        view_model = env["ir.ui.view"]
        form_view_name = f"{cls._name.replace('.', '_')}.form.default.spec.auto"
        tree_view_name = f"{cls._name.replace('.', '_')}.tree.default.spec.auto"

        if not view_model.search_count(
            [("name", "=", form_view_name), ("model", "=", cls._name)]
        ):
            form_arch_str = model_instance._build_default_spec_form_arch(
                spec_prefix_val
            )
            form_view_vals = {
                "name": form_view_name,
                "model": cls._name,
                "arch": form_arch_str,
                "type": "form",
                "priority": 99,
            }
            view_model.create(form_view_vals)
            _logger.info(
                f"Created default form view {form_view_name} for model {cls._name}."
            )
        else:
            _logger.info(
                f"Default form view {form_view_name} already exists for model {cls._name}."
            )

        if not view_model.search_count(
            [("name", "=", tree_view_name), ("model", "=", cls._name)]
        ):
            tree_arch_str = model_instance._get_default_spec_tree_view_arch(
                spec_prefix_val
            )
            tree_view_vals = {
                "name": tree_view_name,
                "model": cls._name,
                "arch": tree_arch_str,
                "type": "tree",
                "priority": 99,
            }
            view_model.create(tree_view_vals)
            _logger.info(
                f"Created default tree view {tree_view_name} for model {cls._name}."
            )
        else:
            _logger.info(
                f"Default tree view {tree_view_name} already exists for model {cls._name}."
            )

    @api.model
    def _build_default_spec_form_arch(self, spec_prefix):
        doc = E.form()
        form_title = self._description or self._name
        doc.set("string", form_title)
        sheet = E.sheet()
        doc.append(sheet)

        spec_arch_fragment, _ = self._build_spec_view_fragment(spec_prefix)

        if spec_arch_fragment is not None and list(spec_arch_fragment):
            if spec_arch_fragment.tag == "group":
                spec_arch_fragment.set("col", "4")
                if not spec_arch_fragment.get("string"):
                    # Use the title from _get_spec_view_page_title for the main fragment group
                    spec_arch_fragment.set(
                        "string", self._get_spec_view_page_title(spec_prefix)
                    )
            sheet.append(spec_arch_fragment)
        else:
            main_group = E.group(col="4")
            # Use the title from _get_spec_view_page_title for the fallback group
            main_group.set("string", self._get_spec_view_page_title(spec_prefix))
            rec_name_to_use = (
                self._rec_name
                if self._rec_name and self._rec_name in self._fields
                else None
            )
            if not rec_name_to_use and "name" in self._fields:
                rec_name_to_use = "name"
            if not rec_name_to_use and "id" in self._fields:
                rec_name_to_use = "id"

            if rec_name_to_use:
                main_group.append(E.field(name=rec_name_to_use))
            else:
                main_group.append(
                    E.label(string=_("No displayable fields configured."))
                )
            sheet.append(main_group)

        return etree.tostring(doc, encoding="unicode")
