<?php
// SPDX-License-Identifier: GPL-2.0-only
// Native IssabelPBX install_amp extracted ordering boundary, original SHA2524787d.
// Original notices remain in the vendor executable; this inert fixture runs only with namespaced stubs.
    // edit conf file passwords and then
    // reload manager in asterisk if it is running:
    //
    if (file_exists(dirname(__FILE__)."/apply_conf.sh")) {
        out("apply username/password changes to conf files:");
        debug("Running ".dirname(__FILE__)."/apply_conf.sh");
        $apply_conf_out = array();
        if ($force_amportal_conf) {
            out("running apply_conf.sh from " . AMP_CONF);
            putenv('FORCE_AMPORTAL_CONF=1');
            exec(dirname(__FILE__)."/apply_conf.sh ".AMP_CONF, $apply_conf_out);
            putenv('FORCE_AMPORTAL_CONF=');
        } else {
            out("running apply_conf.sh from issabelpbx_settings");
            exec(dirname(__FILE__)."/apply_conf.sh", $apply_conf_out);
        }
        foreach ($apply_conf_out as $line) {
            out($line);
        }
        unset($apply_conf_out);
        out("done with apply_conf.sh");
    }

    /* As of Asterisk 1.4.16 or there about, a missing #include file will make the reload fail. So
       we need to make sure that we have such for everything that is in our configs. We will simply
     look for the #include statements and touch the files vs. trying to inventory everything we may
     need and then forgetting something.
     */

    outn("creating missing #include files..");
    $include_err = false;
    exec("grep '#include' ".$amp_conf['ASTETCDIR']."/*.conf | sed 's/;.*//; s/#include//'",$output,$retcode);
    if ($retcode != 0) {
        out("Error code $retcode: trying to search for missing #include files");
        $include_err = true;
    }

    foreach($output as $file) {
        if (trim($file) == '') {
            continue;
        }
        $parse1 = explode(':',$file);
        if(!isset($parse1[1])) { continue; }
        $parse2 = explode(';',$parse1[1]);
        $rawfile = trim($parse2[0]);
        if(substr($rawfile,0,1)=='"' && substr($rawfile,-1)=='"') { $rawfile=substr($rawfile,1,-1); }
        if ($rawfile == '') {
            continue;
        }
        $target = ($rawfile[0] == '/') ? $rawfile : $amp_conf['ASTETCDIR']."/$rawfile";
        if(preg_match("/\*/",$target)) { continue; }

        if (!file_exists($target)) {
            exec("sudo -u $asteriskuser touch $target", $output, $retcode);
            if ($retcode != 0) {
                out("Error code $retcode: trying to create empty file $target");
                $include_err = true;
            }
        }
    }
    if (! $include_err) {
        out("OK");
    }

