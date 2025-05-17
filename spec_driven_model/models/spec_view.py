# spec_driven_model/models/spec_view.py
import logging
from lxml import etree
from lxml.builder import E

from odoo import api, models, _

_logger = logging.getLogger(__name__)

def get_concrete_model_name(env, abstract_model_name):
    from .spec_models import SPEC_MIXIN_MAPPINGS
    return SPEC_MIXIN_MAPPINGS[env.cr.dbname].get(abstract_model_name, abstract_model_name)

class SpecViewMixin(models.AbstractModel):
    _name = "spec.mixin.view"
    _description = "Automatic View Generation for Spec-Driven Models"

    def _get_spec_view_page_title(self, spec_prefix):
        return f"{spec_prefix.upper()} Details"

    def _get_spec_view_field_settings(self, spec_prefix):
        return getattr(self, f"_{spec_prefix}_view_field_settings", {})

    def _get_spec_view_custom_xml_override(self, spec_prefix, path_str):
        return None

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        # Call super() first to get the base view structure
        res = super().get_view(view_id=view_id, view_type=view_type, **options)

        if self._context.get("spec_view_processed") or view_type != 'form':
            return res

        spec_prefix_from_context = self._context.get('spec_prefix')
        current_spec_prefix = None

        if spec_prefix_from_context:
            current_spec_prefix = spec_prefix_from_context
        elif hasattr(self, '_spec_prefix'):
            current_spec_prefix = self._spec_prefix()

        if not current_spec_prefix:
            return res

        schema_part = current_spec_prefix.rstrip('0123456789')
        is_stacked = hasattr(self, f"_{current_spec_prefix}_stacking_mixin")
        has_spec_mixin_in_inherit = any(
            isinstance(base_name, str) and base_name.startswith(f"{schema_part}.")
            for base_name in getattr(self, '_inherit', [])
        )
        is_direct_spec_model = self._name.startswith(f"{schema_part}.")

        if not is_stacked and not has_spec_mixin_in_inherit and not is_direct_spec_model:
            return res

        doc = etree.fromstring(res["arch"]) # Use etree.fromstring for bytes/str
        generated_fields = set()
        view_name_from_res = res.get("name", "default") # Odoo 16 get_view might not have 'name' key sometimes

        injection_point = None
        injection_mode = "page" # Default

        if doc.xpath("//notebook"):
            injection_point = doc.xpath("//notebook")[0]
            injection_mode = "page"
        elif doc.xpath("//sheet"):
            injection_point = doc.xpath("//sheet")[0]
            # Use view_id or a unique view name if 'name' key is unreliable.
            # For simplicity, if 'default' is part of a view's XMLID, it's often the base.
            is_default_view = "default" in str(view_id or '') or "default" in view_name_from_res
            if is_default_view and is_direct_spec_model:
                injection_mode = "replace_sheet_content"
            else:
                injection_mode = "group"
        elif doc.xpath("//form"):
            injection_point = doc.xpath("//form")[0]
            injection_mode = "append_to_form"

        if injection_point is None and is_direct_spec_model:
            doc = E.form()
            sheet = E.sheet()
            doc.append(sheet)
            injection_point = sheet
            injection_mode = "replace_sheet_content"

        if injection_point is not None:
            spec_arch_fragment, new_fields = self._build_spec_view_fragment(current_spec_prefix)
            generated_fields.update(new_fields)

            if spec_arch_fragment is not None and list(spec_arch_fragment):
                page_or_group_title = self._get_spec_view_page_title(current_spec_prefix)
                if injection_mode == "page":
                    page = E.page(string=page_or_group_title)
                    for child in list(spec_arch_fragment): page.append(child)
                    injection_point.append(page)
                elif injection_mode == "group":
                    page_or_group_title = self._get_spec_view_page_title(current_spec_prefix) # Get the title
                    # The fragment itself is usually a group. Add title to it or wrap it.
                    if spec_arch_fragment.tag == "group": # If fragment is already a group
                        spec_arch_fragment.set("string", page_or_group_title) # Set its title
                        spec_arch_fragment.set("col", "4")
                        spec_arch_fragment.set("colspan", "4")
                        injection_point.append(spec_arch_fragment)
                    else: # Wrap if not a group (e.g. fragment is just a sequence of fields)
                        outer_group = E.group(string=page_or_group_title, col="4", colspan="4")
                        for child in list(spec_arch_fragment):
                            outer_group.append(child)
                        injection_point.append(outer_group)

                elif injection_mode == "replace_sheet_content":
                    for child_node in list(injection_point): # injection_point is the <sheet>
                        injection_point.remove(child_node)

                    # spec_arch_fragment is the <group> of spec fields
                    if spec_arch_fragment.tag == "group":
                        spec_arch_fragment.set("col", "4") # Standard layout
                        # Get the desired title for this specific group
                        group_title = self._get_spec_view_page_title(current_spec_prefix)
                        spec_arch_fragment.set("string", group_title) # Set title on the group itself

                    # Set title on the sheet as well, typically from model's description
                    if not injection_point.get("string"): # If sheet has no title
                        injection_point.set("string", self._description or self._name)

                    injection_point.append(spec_arch_fragment)

                elif injection_mode == "append_to_form":
                    for child_node in list(spec_arch_fragment): injection_point.append(child_node)

        # Update res['fields'] for any new fields added by the generator
        # get_view already returns a comprehensive fields dict. We only need to add if missing.
        res_fields = res.get("fields", {}) # Get fields dict safely
        current_fields_info = self.fields_get(allfields=list(generated_fields)) # Get info for generated fields
        for field_name in generated_fields:
            if field_name not in res_fields and field_name in current_fields_info:
                field_info = current_fields_info[field_name]
                if field_info.get("type") in ["one2many", "many2one"]: # Check type safely
                    field_info["views"] = {} # Prevent inline views by default
                res_fields[field_name] = field_info # Add to the res_fields dict
                #res["fields"][field_name] = field_info

        res["fields"] = res_fields
        res["arch"] = etree.tostring(doc, encoding="unicode")

        new_context = dict(self._context, spec_view_processed=True)
        # The recursive call to super().get_view is tricky here.
        # We've modified 'res', which is the result of the *initial* super().get_view.
        # If super().get_view itself has internal caching or state based on the first call,
        # just calling it again might not re-process our modified arch.
        # For `get_view`, it's generally safer to modify `res` and return it,
        # rather than calling super() again with the modified state.
        # The `spec_view_processed` guard is primarily for when this method itself is called recursively
        # from Odoo's view processing for sub-views, not for re-calling super within the same execution.
        return res

    # _build_spec_view_fragment, _recursive_build_view_arch, _apply_common_field_attrs,
    # _get_default_spec_tree_view_arch, _create_default_spec_views, _build_default_spec_form_arch
    # remain largely the same as your last version, with minor logging/robustness tweaks if needed.
    # ... (rest of the SpecViewMixin methods from your previous version)
    # Make sure _build_default_spec_form_arch sets a string on the main sheet/group if it's empty
    # as seen in the failing test.

    @api.model
    def _build_spec_view_fragment(self, spec_prefix):
        generated_fields = set()
        root_container = E.group()

        if hasattr(self, f"_{spec_prefix}_stacking_mixin"):
            stacking_settings_attr = f"_{spec_prefix}_spec_settings"
            stacking_settings_val = getattr(self, stacking_settings_attr, None)
            if not stacking_settings_val:
                 stacking_settings_val = {
                    "odoo_module": getattr(self, f"_{spec_prefix}_odoo_module", None),
                    "stacking_mixin": getattr(self, f"_{spec_prefix}_stacking_mixin", None),
                    "stacking_points": getattr(self, f"_{spec_prefix}_stacking_points", {}),
                    "stacking_skip_paths": getattr(self, f"_{spec_prefix}_stacking_skip_paths", []),
                    "stacking_force_paths": getattr(self, f"_{spec_prefix}_stacking_force_paths", []),
                }

            if not stacking_settings_val or not stacking_settings_val.get("stacking_mixin"):
                _logger.error(f"StackedModel {self._name} misconfigured for spec_prefix {spec_prefix}. Missing stacking_mixin.")
                return None, generated_fields

            start_node_abstract_name = stacking_settings_val["stacking_mixin"]
            start_node_cls = self.env[start_node_abstract_name]
            path_prefix_start = start_node_abstract_name.split('.')[-1]

            self._recursive_build_view_arch(
                spec_prefix, self, start_node_cls, root_container,
                generated_fields, stacking_settings_val, path_prefix_start, depth=0
            )
        else:
            schema_part = spec_prefix.rstrip('0123456789')
            spec_model_name_to_build = None
            if self._name.startswith(f"{schema_part}."):
                spec_model_name_to_build = self._name
            else:
                for base_name in getattr(self, '_inherit', []):
                    if isinstance(base_name, str) and base_name.startswith(f"{schema_part}."):
                        spec_model_name_to_build = base_name
                        break

            if spec_model_name_to_build:
                start_node_cls = self.env[spec_model_name_to_build]
                path_prefix_start = spec_model_name_to_build.split('.')[-1]
                self._recursive_build_view_arch(
                    spec_prefix, self, start_node_cls, root_container,
                    generated_fields, None, path_prefix_start, depth=0
                )
            else:
                _logger.warning(f"Could not determine starting spec node for {self._name} and prefix {spec_prefix}")
                return None, generated_fields

        if not list(root_container):
            return None, generated_fields
        return root_container, generated_fields

    @api.model
    def _recursive_build_view_arch(
        self, spec_prefix, concrete_model_cls, current_spec_node_cls,
        view_parent_node, generated_fields, stacking_settings,
        path_prefix, depth
    ):
        field_settings_for_prefix = concrete_model_cls._get_spec_view_field_settings(spec_prefix)
        custom_xml_str = concrete_model_cls._get_spec_view_custom_xml_override(spec_prefix, path_prefix)

        if custom_xml_str:
            try:
                custom_node = etree.fromstring(custom_xml_str)
                for f_node in custom_node.xpath(".//field"):
                    if f_node.get("name"):
                        generated_fields.add(f_node.get("name"))

                if custom_node.tag in ('group', 'page') or len(list(custom_node)) > 1 and custom_node.tag != 'field': # Field can have children like tree/form for o2m
                    for child in list(custom_node): view_parent_node.append(child)
                else:
                    view_parent_node.append(custom_node)
                return
            except etree.XMLSyntaxError as e:
                _logger.error(f"Error parsing custom XML for {path_prefix} in {concrete_model_cls._name}: {e}")

        if not current_spec_node_cls._fields and current_spec_node_cls._name != concrete_model_cls._name:
            try:
                # Ensure the abstract model's fields are available if it wasn't fully set up
                # This is a bit of a safeguard, normally Odoo registry handles this.
                if not self.env.registry.models.get(current_spec_node_cls._name)._fields_setup:
                    current_spec_node_cls._setup_fields()
            except Exception as e:
                _logger.error(f"Failed to ensure fields setup for {current_spec_node_cls._name}: {e}")
                # Continue if possible, but field iteration might be empty

        fields_on_current_line = 0
        MAX_FIELDS_PER_LINE = 2

        # Sort fields for consistent view generation, e.g., by their definition order if possible
        # Odoo's _fields is an OrderedDict, so iterating it preserves definition order.
        field_items = list(current_spec_node_cls._fields.items())


        for idx, (field_name_on_spec_node, field_obj_on_spec_node) in enumerate(field_items):
            if not field_name_on_spec_node.startswith(spec_prefix + "_") or \
               f"{spec_prefix}_choice" in field_name_on_spec_node:
                continue

            actual_field_name_on_concrete = field_name_on_spec_node
            field_obj_on_concrete = concrete_model_cls._fields.get(actual_field_name_on_concrete)

            if not field_obj_on_concrete:
                 # This field from the abstract spec node is not present on the concrete model.
                 # This could be due to _add_field skipping it (e.g. a stacked M2O itself),
                 # or it's a truly missing field.
                _logger.debug(f"Field {actual_field_name_on_concrete} from spec {current_spec_node_cls._name} not found on concrete model {concrete_model_cls._name}. Skipping for view.")
                continue

            clean_field_name_for_path = actual_field_name_on_concrete[len(spec_prefix)+1:]
            current_field_path = f"{path_prefix}.{clean_field_name_for_path}"
            field_view_config = field_settings_for_prefix.get(actual_field_name_on_concrete, {})

#            if field_view_config.get('invisible') == "1" or field_view_config.get('invisible') is True:
#                continue

            original_comodel_name_on_spec = field_obj_on_spec_node.comodel_name
            actual_comodel_name_on_concrete = None
            if original_comodel_name_on_spec:
                actual_comodel_name_on_concrete = get_concrete_model_name(self.env, original_comodel_name_on_spec)

            is_field_stacked_by_config = False
            if stacking_settings and field_name_on_spec_node in stacking_settings.get("stacking_points", {}):
                _logger.info(f"Field {field_name_on_spec_node} IS a stacking point. Type: {field_obj_on_spec_node.type}, Comodel: {original_comodel_name_on_spec}")
                if stacking_settings and field_obj_on_spec_node.type == 'many2one' and original_comodel_name_on_spec:
                    if actual_field_name_on_concrete in stacking_settings.get("stacking_points", {}):
                        is_field_stacked_by_config = True
                else:
                    _logger.warning(f"Field {field_name_on_spec_node} is stacking point BUT not M2O or no comodel.")

            if is_field_stacked_by_config:
                _logger.info(f"STACKED VIEW: Field '{field_name_on_spec_node}' is stacked. Path: {current_field_path}")
                if fields_on_current_line > 0:
                    view_parent_node.append(E.newline())
                    fields_on_current_line = 0

                group_label = field_obj_on_concrete.string or clean_field_name_for_path.capitalize()

                # If the view_parent_node is a 'group', nested groups are fine.
                # If it's a 'page' or 'sheet', we might want to ensure a 'group' wrapper.
                current_parent_for_stack = view_parent_node
                if view_parent_node.tag not in ('group', 'page'): # 'page' can contain groups directly
                    # This case might need more thought if view_parent_node is 'form' or 'sheet' directly
                    group_wrapper_for_stack = E.group(colspan="4") # Make it full width
                    view_parent_node.append(group_wrapper_for_stack)
                    current_parent_for_stack = group_wrapper_for_stack

                inner_group = E.group(string=group_label, colspan="4")
                self._apply_common_field_attrs(inner_group, field_view_config, field_obj_on_concrete)
                current_parent_for_stack.append(inner_group)

                stacked_abstract_spec_model_cls = self.env[original_comodel_name_on_spec]
                self._recursive_build_view_arch(
                    spec_prefix, concrete_model_cls, stacked_abstract_spec_model_cls,
                    inner_group, generated_fields, stacking_settings,
                    current_field_path, depth + 1 # Increment depth for stacked group
                )
                fields_on_current_line = 0
                continue

            if field_obj_on_concrete.type == 'one2many' and actual_comodel_name_on_concrete:
                _logger.info(f"REGULAR M2O VIEW: Field '{actual_field_name_on_concrete}'. Path: {current_field_path}")
                if fields_on_current_line > 0: view_parent_node.append(E.newline())
                generated_fields.add(actual_field_name_on_concrete)
                o2m_field_node = E.field(name=actual_field_name_on_concrete, nolabel="0", colspan="4")

                o2m_line_model = self.env[actual_comodel_name_on_concrete]
                o2m_tree = E.tree()
                o2m_form = E.form()

                line_field_count_tree = 0
                MAX_O2M_TREE_FIELDS = 4

                # Add _rec_name to tree if exists and simple
                if o2m_line_model._rec_name and o2m_line_model._rec_name in o2m_line_model._fields and \
                   o2m_line_model._fields[o2m_line_model._rec_name].type not in ['one2many', 'many2many', 'binary']:
                    o2m_tree.append(E.field(name=o2m_line_model._rec_name))
                    generated_fields.add(f"{actual_field_name_on_concrete}.{o2m_line_model._rec_name}")
                    line_field_count_tree +=1

                for line_fname, line_fobj in o2m_line_model._fields.items():
                    if line_fname == o2m_line_model._rec_name: continue # Already added or will be
                    if not line_fobj.automatic and line_fobj.store and \
                       line_fobj.type not in ['one2many', 'many2many', 'binary'] and \
                       not line_fname.startswith(spec_prefix + "_choice"): # Avoid choice selectors in o2m tree/form
                        if line_field_count_tree < MAX_O2M_TREE_FIELDS:
                            o2m_tree.append(E.field(name=line_fname))
                            line_field_count_tree +=1
                        o2m_form.append(E.field(name=line_fname))
                        generated_fields.add(f"{actual_field_name_on_concrete}.{line_fname}")

                if line_field_count_tree == 0 and 'id' in o2m_line_model._fields: # Fallback if no suitable fields
                    o2m_tree.append(E.field(name='id'))
                    generated_fields.add(f"{actual_field_name_on_concrete}.id")


                o2m_field_node.append(o2m_tree)
                o2m_field_node.append(o2m_form) # Odoo client uses this form for pop-ups or inline editing
                self._apply_common_field_attrs(o2m_field_node, field_view_config, field_obj_on_concrete)
                view_parent_node.append(o2m_field_node)
                fields_on_current_line = 0
                continue

            elif field_obj_on_concrete.type == 'many2one' and actual_comodel_name_on_concrete:
                generated_fields.add(actual_field_name_on_concrete)
                m2o_field_node = E.field(name=actual_field_name_on_concrete)
                self._apply_common_field_attrs(m2o_field_node, field_view_config, field_obj_on_concrete)
                view_parent_node.append(m2o_field_node)
                fields_on_current_line += 1

            elif field_obj_on_concrete.type not in ['binary', 'reference', 'serialized', 'one2many', 'many2many']:
                generated_fields.add(actual_field_name_on_concrete)
                simple_field_node = E.field(name=actual_field_name_on_concrete)
                if field_obj_on_concrete.type in ('text', 'html') and not field_view_config.get('colspan'):
                    simple_field_node.set("colspan", "4")

                self._apply_common_field_attrs(simple_field_node, field_view_config, field_obj_on_concrete)
                view_parent_node.append(simple_field_node)
                fields_on_current_line += 1

            is_last_field_in_node = (idx == len(field_items) - 1)
            if fields_on_current_line >= MAX_FIELDS_PER_LINE and not is_last_field_in_node :
                 view_parent_node.append(E.newline())
                 fields_on_current_line = 0

    def _apply_common_field_attrs(self, lxml_node, field_view_config, field_obj):
        """Applies common view attributes from config to an lxml node.
           field_obj is the Odoo field object from the concrete model.
        """
        attrs_dict = {}
        try: # Load existing attrs from node if any
            existing_attrs_str = lxml_node.get("attrs")
            if existing_attrs_str:
                attrs_dict = eval(existing_attrs_str)
        except Exception:
            attrs_dict = {}

        for static_attr_name in ['widget', 'options', 'placeholder', 'nolabel', 'colspan', 'string', 'help', 'sum', 'avg']: # Non-boolean attributes
            if static_attr_name in field_view_config:
                lxml_node.set(static_attr_name, str(field_view_config[static_attr_name]))

        # Handle boolean-like XML attributes (invisible, readonly, required)
        for bool_attr_name in ['invisible', 'readonly', 'required']:
            if bool_attr_name in field_view_config:
                val = field_view_config[bool_attr_name]
                if val == "1" or val is True:
                    lxml_node.set(bool_attr_name, "1") # Direct XML attribute for static true
                elif isinstance(val, str) and (val.startswith("[") or val.startswith("(")):
                    # If it's a domain string, put it in attrs
                    try:
                        attrs_dict[bool_attr_name] = eval(val)
                    except Exception as e:
                        _logger.error(f"Failed to eval {bool_attr_name} string '{val}' for field {lxml_node.get('name')}: {e}")
                # If val is "0" or False, we explicitly do NOT set the attribute from config,
                # allowing Odoo/field defaults to take precedence or for it to be simply not present.

        # Dynamic attributes via 'attrs' key in config (merges with above)
        if 'attrs' in field_view_config:
            try:
                config_attrs = eval(field_view_config['attrs'])
                if isinstance(config_attrs, dict):
                    for key, value in config_attrs.items():
                        attrs_dict[key] = value
            except Exception as e:
                 _logger.error(f"Failed to eval 'attrs' string '{field_view_config['attrs']}' for field {lxml_node.get('name')}: {e}")

        # Apply collected attrs_dict to the node
        if attrs_dict:
            # Odoo expects attrs values to be lists/tuples, not direct booleans.
            # Ensure static true/false are represented as domain-like expressions.
            final_attrs_dict = {}
            for k, v_attr in attrs_dict.items():
                if v_attr is True or v_attr == "1":
                    final_attrs_dict[k] = [("1", "=", "1")] # Represents static True
                elif v_attr is False or v_attr == "0":
                     final_attrs_dict[k] = [("1", "=", "0")] # Represents static False
                else:
                    final_attrs_dict[k] = v_attr # Assumed to be correctly formatted list/tuple
            if final_attrs_dict:
                lxml_node.set("attrs", str(final_attrs_dict))

        # Add 'required="1"' if the Odoo field object itself is marked as required
        # and not already handled by attrs or field_view_config
        if field_obj and field_obj.required and not lxml_node.get("required") and 'required' not in attrs_dict:
            if not field_view_config.get('required') == "0" and not field_view_config.get('required') is False: # Not explicitly set to non-required
                lxml_node.set("required", "1")


    @api.model
    def _get_default_spec_tree_view_arch(self, spec_prefix):
        tree = E.tree()
        count = 0
        added_fields = set()
        MAX_TREE_FIELDS = 7

        # Check concrete model's _rec_name first
        concrete_rec_name = self._rec_name
        if concrete_rec_name and concrete_rec_name in self._fields and \
           concrete_rec_name.startswith(spec_prefix + "_") and concrete_rec_name not in added_fields:
            tree.append(E.field(name=concrete_rec_name))
            added_fields.add(concrete_rec_name)
            count += 1

        for fname, field in self._fields.items():
            if count >= MAX_TREE_FIELDS: break
            if fname == concrete_rec_name: continue # Already added or will be prioritized

            if fname.startswith(spec_prefix + "_") and \
               not field.automatic and field.store and \
               field.type not in ['one2many', 'many2many', 'binary', 'html', 'text'] and \
               fname not in added_fields and \
               not fname.startswith(spec_prefix + "_choice"):
                tree.append(E.field(name=fname))
                added_fields.add(fname)
                count += 1

        if count == 0: # Fallback if no spec fields suitable
            if concrete_rec_name and concrete_rec_name in self._fields:
                 tree.append(E.field(name=concrete_rec_name))
            elif 'name' in self._fields:
                 tree.append(E.field(name='name'))
            elif 'id' in self._fields:
                 tree.append(E.field(name='id'))
        return etree.tostring(tree, encoding="unicode")

    @classmethod
    def _create_default_spec_views(cls, env, module_name):
        if not hasattr(cls, '_spec_prefix'):
            _logger.warning(f"Model {cls._name} lacks _spec_prefix, cannot auto-create default views.")
            return

        # Instantiate to call instance methods like _spec_prefix if needed by some hooks
        # This requires cls to be a registered model.
        model_instance = env[cls._name]
        spec_prefix_val = model_instance._spec_prefix()
        if not spec_prefix_val:
            _logger.warning(f"Cannot determine spec_prefix for {cls._name}, skipping default view creation.")
            return

        # Check if views already exist to prevent duplicates during re-installs/updates
        view_model = env['ir.ui.view']
        form_view_name = f"{cls._name.replace('.', '_')}.form.default.spec.auto"
        tree_view_name = f"{cls._name.replace('.', '_')}.tree.default.spec.auto"

        if not view_model.search_count([('name', '=', form_view_name), ('model', '=', cls._name)]):
            form_arch_str = model_instance._build_default_spec_form_arch(spec_prefix_val)
            form_view_vals = {
                'name': form_view_name, 'model': cls._name,
                'arch': form_arch_str, 'type': 'form', 'priority': 99,
            }
            view_model.create(form_view_vals)
        else:
            _logger.info(f"Default form view {form_view_name} already exists for model {cls._name}.")


        if not view_model.search_count([('name', '=', tree_view_name), ('model', '=', cls._name)]):
            tree_arch_str = model_instance._get_default_spec_tree_view_arch(spec_prefix_val)
            tree_view_vals = {
                'name': tree_view_name, 'model': cls._name,
                'arch': tree_arch_str, 'type': 'tree', 'priority': 99,
            }
            view_model.create(tree_view_vals)
        else:
            _logger.info(f"Default tree view {tree_view_name} already exists for model {cls._name}.")


    @api.model
    def _build_default_spec_form_arch(self, spec_prefix):
        # self here is an instance of the model, created by cls(env, None) in _create_default_spec_views
        doc = E.form()
        # Add model description or name to the form string if it's a default view for an auto-gen model
        form_title = self._description or self._name
        doc.set("string", form_title)

        sheet = E.sheet()
        doc.append(sheet)

        spec_arch_fragment, _ = self._build_spec_view_fragment(spec_prefix)

        if spec_arch_fragment is not None and list(spec_arch_fragment):
            # The fragment is usually a group. For a base form, this group can be the main content.
            if spec_arch_fragment.tag == "group":
                spec_arch_fragment.set("col", "4") # Standard for a main group in a sheet
                # If the group itself has no title, give it one for clarity
                if not spec_arch_fragment.get("string"):
                     spec_arch_fragment.set("string", f"{spec_prefix.upper()} Data")
            sheet.append(spec_arch_fragment)
        else: # Fallback content
            main_group = E.group(col="4") # Ensure a group wrapper
            rec_name_to_use = self._rec_name if self._rec_name in self._fields else 'id'
            if rec_name_to_use not in self._fields and 'name' in self._fields:
                rec_name_to_use = 'name'

            if rec_name_to_use in self._fields:
                main_group.append(E.field(name=rec_name_to_use))
            else:
                 main_group.append(E.label(string="No displayable fields configured for this auto-generated view."))
            sheet.append(main_group)

        return etree.tostring(doc, encoding="unicode")
