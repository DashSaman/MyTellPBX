<?php
// Evaluate only the REST classes with persistence replaced by argument capture.
// No database, calendar file, email or Asterisk dependencies are loaded.
class REST_Resource {}
class paloSantoJSON {}
class core_Calendar {
    static $args;
    function editCalendarEvent(...$args) { self::$args=$args; return true; }
    function addCalendarEvent(...$args) { self::$args=$args; return 100; }
}
define('REST_CALENDAR_BASEURL','/rest.php/calendar/CalendarEvent/');
$source=file_get_contents($argv[1]);
eval(substr($source,strpos($source,'class CalendarEvent')));
$_SERVER['CONTENT_TYPE']='application/x-www-form-urlencoded';
$tests=array();
$api=new CalendarEventById('99');
$_POST=array('startdate'=>'2026-11-15 10:00:00','enddate'=>'2026-11-15 11:00:00');
$api->HTTP_POST();
$tests['partial time update preserves omitted notification field']=core_Calendar::$args[10]===null;
$_POST=array('clear_notifications'=>'1');$api->HTTP_POST();
$tests['explicit notification clear reaches storage as empty array']=core_Calendar::$args[10]===array();
$_POST=array('clear_notifications'=>'0','emails_notification'=>array('fixture@example.invalid'));$api->HTTP_POST();
$tests['existing notification array remains intact']=core_Calendar::$args[10]===array('fixture@example.invalid');
$_POST=array('clear_notifications'=>'1','asterisk_call'=>'false');(new CalendarEventBase())->HTTP_POST();
$tests['create with reminders disabled cannot enable a call']=core_Calendar::$args[4]===false;
$tests['create clear intent is empty array']=core_Calendar::$args[9]===array();
foreach($tests as $name=>$pass)echo($pass?'PASS ':'FAIL ').$name."\n";
exit(in_array(false,$tests,true)?1:0);
