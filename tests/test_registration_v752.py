from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_registration_ux():
    js=(ROOT/'frontend/registration-ux.js').read_text(encoding='utf-8')
    handler=(ROOT/'frontend/registration-handler.js').read_text(encoding='utf-8')
    idx=(ROOT/'frontend/index.html').read_text(encoding='utf-8')
    for x in [
        '3–24 znaki',
        'Minimum 8 znaków',
        'validateAll',
        'reg-inline-v78c5',
        'Np. TenisFan87',
    ]:
        assert x in js
    assert 'RATE_KEY' in handler
    assert 'new MutationObserver' not in js
    assert '.focus(' not in js
    assert 'src="registration-handler.js"' in idx
    assert 'src="registration-ux.js"' in idx
    assert 'href="registration-ux.css"' in idx
    for retired in ('registration-fix-v741.js','registration-ux-v752.js','registration-ux-v752.css'):
        assert retired not in idx
        assert not (ROOT/'frontend'/retired).exists()


def test_concurrent_captcha_initializers_mount_only_one_widget():
    import shutil
    import subprocess
    import pytest
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for auth UI regression tests')
    subprocess.run([node, '-e', r'''
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
let renderCount=0;
const host={isConnected:true};
const shell={dataset:{},querySelector:()=>host};
const form={elements:{},querySelector:()=>shell};
let initClick;
const window={turnstile:{render(){renderCount++;return 'widget-1';},remove(){}}};
const ctx=vm.createContext({window,setTimeout:fn=>fn(),
 document:{querySelector:s=>s==='#account-auth-form'?form:s==='#tenis-ai-turnstile-style'?{}:null,
 addEventListener(type,fn){if(type==='click')initClick=fn;}}});
vm.runInContext(fs.readFileSync('frontend/registration-ux.js','utf8'),ctx);
initClick();initClick();
Promise.resolve().then(()=>{
 assert.equal(renderCount,1,'shared script load must not produce duplicate widgets');
 initClick();
 return Promise.resolve();
}).then(()=>assert.equal(renderCount,1,'later init retains the completed widget'));
'''], cwd=ROOT, check=True)
