# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

# Monkey-patch xsdata XmlContext to properly handle NFe namespace
# for classes from dfe_tipos_basicos_v1_00 which don't declare it
from xsdata.formats.dataclass.context import XmlContext

_original_fetch = XmlContext.fetch


def _patched_fetch(self, clazz, parent_ns=None, xsi_type=None):
    if clazz.__module__ == "nfelib.nfe.bindings.v4_0.dfe_tipos_basicos_v1_00":
        parent_ns = parent_ns or "http://www.portalfiscal.inf.br/nfe"
    return _original_fetch(self, clazz, parent_ns, xsi_type)


XmlContext.fetch = _patched_fetch

from .hooks import post_init_hook  # noqa: E402
from . import models  # noqa: E402
from . import wizards  # noqa: E402
from . import report  # noqa: E402
