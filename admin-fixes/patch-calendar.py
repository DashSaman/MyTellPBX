"""Plan exact, reversible changes to the installed Issabel calendar module."""
from pathlib import Path
import re


def replace(text, old, new, count=1):
    if text.count(new) == count:
        return text
    if new in text:
        raise ValueError('Partial calendar patch near: ' + new[:90])
    if text.count(old) != count:
        raise ValueError('Calendar source drift near: ' + old[:90])
    return text.replace(old, new)


def javascript(text):
    text = replace(text, 'firstDay: 1,', 'firstDay: 6,', 2)
    text = replace(text, "events: '/rest.php/' + getCurrentIssabelModule() + '/CalendarEvent?format=fullcalendar',", '/* Civil-date views own their exact REST ranges; no duplicate Gregorian feed. */\n        events: function(start,end,callback) { callback([]); },\n        axisFormat: "HH:mm",\n        buttonText: {today:"امروز",month:"ماه",week:"هفته",day:"روز"},')
    text = replace(text, 'event.start.toISOString()', 'window.MTCalendarCore.serialize(event.start)', 2)
    text = replace(text, 'event.end.toISOString()', 'window.MTCalendarCore.serialize(event.end || new Date(event.start.getTime()+3600000))', 2)
    text = replace(text, 'formatdate(new Date)', 'window.MTCalendarCore.nowText().slice(0,16)')
    text = replace(text, "    $(':input[name=\"to\"]').val(today_str);", "    $(':input[name=\"to\"]').val(window.MTCalendarCore.addMinutes(today_str,60));")
    text = replace(text, 'formatdate($.fullCalendar.parseISO8601(eventdata.starttime))', "window.MTCalendarCore.serialize(eventdata.starttime).slice(0,16)")
    text = replace(text, 'formatdate($.fullCalendar.parseISO8601(eventdata.endtime))', "window.MTCalendarCore.serialize(eventdata.endtime).slice(0,16)")
    text = replace(text, "    $('#grilla').hide();\n}", "    $('#grilla').hide();\n    window.MTCalendarNative.color('#245cc5');\n    window.MTCalendarNative.sync();\n}")
    text = replace(text, '    // Campos de llamada de recordatorio\n    if (eventdata.reminder_timer', '    window.MTCalendarNative.color(eventdata.color);\n    window.MTCalendarNative.sync();\n    // Campos de llamada de recordatorio\n    if (eventdata.reminder_timer')
    text = replace(text, 'function saveEventDialog(url)\n{\n    var postvars', 'function saveEventDialog(url)\n{\n    if (!window.MTCalendarNative.validate()) return null;\n    var postvars')
    text = replace(text, '    return $.post(url, postvars);', '    return window.MTCalendarNative.save(url, postvars);')
    old = "    var m = /^(\\d+)-(\\d+)-(\\d+) (\\d+):(\\d+)$/.exec(s);\n    return new Date(m[1], parseInt(m[2]) - 1, m[3], m[4], m[5]).toISOString();"
    text = replace(text, old, '    return window.MTCalendarCore.serialize(s);')
    start = text.index('function openEventDialog(url)\n{')
    end = text.index('// Limpiar el diálogo', start)
    text = text[:start] + 'function openEventDialog(url)\n{\n    window.MTCalendarNative.open(url);\n}\n\n' + text[end:]
    # Malformed/expired-session HTML must not throw a second parse exception.
    text = re.sub(r"result = \$\.parseJSON\(result.responseText\);\s*alert\([^\n]+\);", 'window.MTCalendarNative.error(result);', text)
    return text


def rest(text):
    # An omitted field remains a partial update. Explicit clear is distinct.
    anchor = '        $postkeys = array_keys($_POST);'
    replacement = """        // MyTellPBX calendar v752: explicit clearing survives form encoding.
        if (isset($_POST['clear_notifications']) && $_POST['clear_notifications'] === '1') {
            $_POST['emails_notification'] = array();
        }
        $postkeys = array_keys($_POST);"""
    return replace(text, anchor, replacement, 2)


def plan(module, resource):
    module, resource = Path(module), Path(resource)
    js = module / 'themes/default/js/javascript.js'
    index = module / 'index.php'
    template = module / 'themes/default/calendar_gui.tpl'
    index_text = index.read_text(encoding='utf-8')
    anchor = "    return $smarty->fetch($local_templates_dir.'/calendar_gui.tpl');"
    index_text = replace(index_text, anchor, "    $smarty->assign('SERVER_TIMEZONE', date_default_timezone_get());\n" + anchor)
    tpl = template.read_text(encoding='utf-8')
    tpl = replace(tpl, '<table class="tabForm"', '<table class="mt-calendar-layout"')
    anchor = '<input type="hidden" name="server_year"'
    tpl = replace(tpl, anchor, '<input type="hidden" name="server_timezone" value="{$SERVER_TIMEZONE|escape:\'html\'}" />\n' + anchor)
    return {js:javascript(js.read_text(encoding='utf-8')), index:index_text, template:tpl, resource:rest(resource.read_text(encoding='utf-8'))}
