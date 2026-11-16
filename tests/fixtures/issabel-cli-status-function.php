<?php
/*
 * Extracted unchanged from Issabel 5 issabel-admin-passwords.
 * Copyright (c) 2023 Issabel Foundation.
 * Copyright (c) 2006 Palosanto Solutions S. A.
 * SPDX-License-Identifier: GPL-2.0-only
 * Distributed without warranty under GNU GPL version 2:
 * https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
 * Whole-source SHA256:
 * aa1a9bc962d5f34c57483d802b7f5e1e010133d2bf3245dc07b644387d9ef410
 * This fixture executes only with a namespaced fake system() in cli-status.php.
 */
function dialog_infobox($backtitle, $msgbox, $height, $width)
{
    $height = (int)$height;
    $width = (int)$width;
    system('/usr/bin/dialog'.
        ' --stdout --sleep 1 --backtitle '.escapeshellarg($backtitle).
        ' --infobox '.escapeshellarg($msgbox).
        " $height $width");
}
