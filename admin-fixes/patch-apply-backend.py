"""Plan the scoped Apply repair. No live writes when imported or invoked.

The owner explicitly requested Apply bug repairs on 2026-11-10. This is a
separate backend patch from the earlier UI-only rollout, with exact anchors.
"""
from pathlib import Path

SOURCE = Path(__file__).resolve().parent
OLD_HANDLER = """        // AJAX handler for reload event
        $response = do_reload();
        header("Content-type: application/json");
        echo json_encode($response);
"""
NEW_HANDLER = """        // MyTellPBX guarded Apply v752: authentication has already passed.
        if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
            http_response_code(405);
            header('Allow: POST');
            $response = array('status'=>false, 'num_errors'=>1, 'message'=>'POST is required.');
        } else {
            require_once __DIR__ . '/mytell-apply.php';
            $response = mytell_apply_authorized($_SESSION['AMP_user'], $_SERVER)
                ? mytell_guarded_reload('do_reload')
                : array('status'=>false, 'num_errors'=>1, 'message'=>'Apply permission or same-origin request proof is missing.', 'http_status'=>403);
            if (isset($response['http_status'])) {
                http_response_code($response['http_status']);
                unset($response['http_status']);
            }
        }
        header("Content-type: application/json");
        echo json_encode($response);
"""
OLD_AMI = """      $astman->Reload();
  }

    $return['status'] = true;"""
NEW_AMI = """      // MyTellPBX v752: AMI rejection is not a successful Apply.
      $reload_response = $astman->Reload();
      if (!is_array($reload_response) || !isset($reload_response['Response']) ||
          strcasecmp($reload_response['Response'], 'Success') !== 0) {
          $return['status'] = false;
          $return['message'] = __('Asterisk did not confirm the configuration reload.');
          $return['num_errors']++;
          $notify->add_critical('issabelpbx', 'RCONFFAIL', __('Configuration reload failed'), $return['message']);
          return $return;
      }
  }

    $return['status'] = true;"""


def replace_once(text, old, new, label):
    if new in text:
        return text
    if text.count(old) != 1:
        raise ValueError('Unexpected installed Apply source: ' + label)
    return text.replace(old, new, 1)


def plan(admin):
    admin = Path(admin)
    handler = admin / 'libraries/view.functions.php'
    functions = admin / 'functions.inc.php'
    return {
        handler: replace_once(handler.read_text(encoding='utf-8'), OLD_HANDLER, NEW_HANDLER, 'handler'),
        functions: replace_once(functions.read_text(encoding='utf-8'), OLD_AMI, NEW_AMI, 'AMI result'),
        admin / 'libraries/mytell-apply.php': (SOURCE / 'reload-guard.php').read_text(encoding='utf-8'),
    }


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('admin_root', type=Path)
    args = parser.parse_args()
    for path, content in plan(args.admin_root).items():
        print('WOULD UPDATE' if not path.exists() or path.read_text(encoding='utf-8') != content else 'UNCHANGED', path)
