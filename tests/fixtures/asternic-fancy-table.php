<?php
/* SPDX-License-Identifier: GPL-3.0-or-later
 * Asternic 1.6.6's audited FancyTable method, isolated for renderer tests.
 * No framework, database or real report data is included.
 */
class PDF extends FPDF
{
    function FancyTable($header,$data,$w) {

        $this->TableHeader($header,$w);

        //Color and font restoration
        $this->SetFillColor(224,235,255);
        $this->SetTextColor(0);
        $this->SetFont('');
        //Data
        $fill=0;
        $supercont=1;
        foreach($data as $row) {
            $contador=0;
            foreach($row as $valor) {
                $this->Cell($w[$contador],6,$valor,'LR',0,'C',$fill);
                $contador++;
            }
            $this->Ln();
            $fill=!$fill;
            if($supercont%40 == 0) {
                $this->Cell(array_sum($w),0,'','T');
                $this->AddPage();
                $this->TableHeader($header,$w);
                $this->SetFillColor(224,235,255);
                $this->SetTextColor(0);
                $this->SetFont('');
            }
            $supercont++;
        }
        $this->Cell(array_sum($w),0,'','T');
    }
}

function asternic_export_csv($header,$data) {
    // Unrelated fixture sentinel: renderer changes must leave CSV untouched.
    return array($header,$data);
}
