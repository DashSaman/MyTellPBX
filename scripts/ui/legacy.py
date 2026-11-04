"""Narrow, fail-closed fixes to installed presentation assets; no PBX actions."""
import re

COLRESIZE_OLD = "onResize=function(){for(t in tables){var t=tables[t],i,mw=0;"
COLRESIZE_NEW = (
    "onResize=function(){for(var tableId in tables){"
    "if(!Object.prototype.hasOwnProperty.call(tables,tableId))continue;"
    "var t=tables[tableId],i,mw=0;"
)
ASTERNIC_OLD = '@import url("themes/default/css/mytel.css?v=mytel-1");'
ASTERNIC_NEW = '@import url("/admin/modules/asternic_cdr/themes/default/css/mytel.css?v=mytel-1");'
GEOIP_HOME = re.compile(
    r"(?P<indent>^[ \t]*)homeLatitude  = homePolygon\.visualLatitude;", re.MULTILINE
)


def replace_once(text, old, new):
    if text.count(old) == 1 and new not in text:
        return text.replace(old, new, 1)
    if text.count(new) == 1 and old not in text:
        return text
    raise ValueError("Installed presentation asset anchor changed")


def colresize(text):
    # Ember extends Array.prototype; the plugin's table registry is an array.
    # Never mistake inherited enumerable methods for registered jQuery tables.
    return replace_once(text, COLRESIZE_OLD, COLRESIZE_NEW)


def asternic(text):
    # This sheet is served by /admin/config.php?handler=file, not its disk URL.
    return replace_once(text, ASTERNIC_OLD, ASTERNIC_NEW)


def geoip(text):
    matches = list(GEOIP_HOME.finditer(text))
    if len(matches) != 2 or text.count("homePolygon   = polygonSeries.getPolygonById(home);") != 2:
        raise ValueError("GeoIP home fallback anchors changed")
    guarded = text.count("if (!homePolygon) return;")
    if guarded == 2:
        for match in matches:
            if not text[:match.start()].endswith(match.group('indent') + "if (!homePolygon) return;\n"):
                raise ValueError("GeoIP fallback guard moved")
        return text
    if guarded:
        raise ValueError("Partially patched GeoIP fallback")
    # A blocked/aborted geolocation request or unknown country must not fabricate
    # coordinates or dereference a polygon already removed during navigation.
    return GEOIP_HOME.sub(lambda m: m.group('indent') + "if (!homePolygon) return;\n" + m.group(0), text)


def plan(roots):
    targets = (
        ('legacy', 'libs/js/jquery/jquery-upl-colResizable-1.5.min.js', colresize),
        ('legacy', 'modules/sec_geoip_map/themes/default/map.tpl', geoip),
        ('admin', 'modules/asternic_cdr/asternic_cdr.css', asternic),
    )
    return {(root, relative): transform((roots[root] / relative).read_text(encoding='utf-8'))
            for root, relative, transform in targets}
