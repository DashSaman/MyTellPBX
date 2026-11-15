<?php
/* Run the captured exact FancyTable method against the actual PHP7 legacy
 * Cell comparison. No real PDF/framework/database/report source is executed.
 * Optional second input is the captured vendor source, read as text only.
 */
$source=file_get_contents($argv[1]);
$start=strpos($source, '    function FancyTable($header,$data,$w) {');
$end=$start === false ? false : strpos($source, "\n}\n\nfunction asternic_export_csv", $start);
if ($start === false || $end === false) throw new RuntimeException('Unknown captured FancyTable boundary');
$method=substr($source,$start,$end-$start);
if (substr_count($method,'function ') !== 1) throw new RuntimeException('Unexpected captured renderer method');
if (isset($argv[2])) {
    $vendor=file_get_contents($argv[2]);
    $cell=strpos($vendor,'function Cell('); $multi=$cell === false ? false : strpos($vendor,'function MultiCell(', $cell);
    if ($cell === false || $multi === false || strpos(substr($vendor,$cell,$multi-$cell), "if(\$txt!='')") === false)
        throw new RuntimeException('Captured vendor does not have the audited legacy Cell boundary');
}
class LegacyCellBoundary {
    public $visible=array(), $dataValues=array(), $headers=array(), $pages=0;
    public function TableHeader($header,$width) { $this->headers[]=array($header,$width); }
    public function SetFillColor(...$args) {}
    public function SetTextColor(...$args) {}
    public function SetFont(...$args) {}
    public function Ln() {}
    public function AddPage() { $this->pages++; }
    public function Cell($width,$height=0,$txt='',$border=0,$line=0,$align='',$fill=0) {
        if ($height === 6 && $border === 'LR') {
            $this->dataValues[]=$txt;
            // Exact audited FPDF Cell guard; execute PHP's real comparison.
            if($txt!='') $this->visible[]=(string)$txt;
        }
    }
}
$temporary=tempnam(sys_get_temp_dir(),'asternic-pdf-method-');
try {
    file_put_contents($temporary,"<?php\nclass CapturedAsternicTable extends LegacyCellBoundary {\n".$method."\n}\n");
    require $temporary;
} finally { unlink($temporary); }
$input=array(0,0.0,'0',8,'0.00','00:00','',null,7.25);
$copy=$input; $header=array_fill(0,count($input),'Fixture'); $width=array_fill(0,count($input),20);
$pdf=new CapturedAsternicTable();$pdf->FancyTable($header,array($input),$width);
$tests=array();
$tests['all seven nonempty scalar cells are visible']=count($pdf->visible)===7;
$tests['integer and float zero render as literal zero']=$pdf->visible===array('0','0','0','8','0.00','00:00','7.25');
$tests['every data value reaches Cell as a string']=count(array_filter($pdf->dataValues,'is_string'))===count($input);
$tests['original typed export data stays unchanged']=$input===$copy;
$tests['header and widths stay unchanged']=$pdf->headers===array(array($header,$width));
$tests['blank and null remain blank']=$pdf->dataValues[6]==='' && $pdf->dataValues[7]==='';
$paged=new CapturedAsternicTable();$paged->FancyTable(array('Count'),array_fill(0,41,array(0)),array(20));
$tests['pagination still emits every zero row']=count($paged->visible)===41 && count($paged->dataValues)===41;
$tests['native forty-row page boundary stays unchanged']=$paged->pages===1 && count($paged->headers)===2;
foreach($tests as $name=>$pass)echo($pass?'PASS ':'FAIL ').$name."\n";
exit(in_array(false,$tests,true)?1:0);
