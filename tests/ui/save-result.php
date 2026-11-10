<?php
/* Evaluate only the result-marker block. No framework, database or settings. */
$source = file_get_contents($argv[1]);
if (!preg_match('/<\?php \/\* MyTellPBX native save result v753:.*?\*\/(.*?)\?>/s', $source, $match)) {
    throw new RuntimeException('Missing result block');
}
$token = str_repeat('a',32);
$cases = array(
    array('POST','edit',$token,true,'success'),
    array('POST','edit',$token,array('invalid'),'validation-error'),
    array('POST','edit',$token,'true','validation-error'),
    array('GET','edit',$token,true,''),
    array('POST','other',$token,true,''),
    array('POST','edit','<img src=x>',true,''),
    array('POST','edit',array($token),true,''),
    array('POST','edit',str_repeat('A',32),true,''),
);
foreach ($cases as $i=>$case) {
    list($method,$action,$attempt,$errors,$expected)=$case;
    $_SERVER['REQUEST_METHOD']=$method; $_POST=array('mt_save_attempt'=>$attempt);
    ob_start(); eval($match[1]); $result=ob_get_clean();
    if ($expected==='') $ok=$result==='';
    else $ok=strpos($result,'data-attempt="'.$token.'"')!==false && strpos($result,'data-status="'.$expected.'"')!==false;
    if (!$ok) throw new RuntimeException('Marker assertion failed: '.$i);
}
echo "PASS 8 native save result boundaries; no persistence executed\n";
