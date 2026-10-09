"""Bounded browser verification of the separate UX prototype (requires Playwright)."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
screenshots = root / 'docs/mockups/screenshots'
screenshots.mkdir(exist_ok=True)
report = {'screens': [], 'interactions': [], 'console_errors': []}
base = os.environ.get('PARAMETRIC_MOCKUP_URL', 'http://127.0.0.1:8765/mockups')
executable = os.environ.get('PARAMETRIC_BROWSER_EXECUTABLE', '/home/bbalazs/.cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell')
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=executable, headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1080}, device_scale_factor=1)
    page.on('pageerror', lambda e: report['console_errors'].append(str(e)))
    for stage in ('connect','plan','capture','train','review'):
        page.goto(f'{base}/index.html?screen={stage}')
        page.evaluate('document.fonts.ready')
        page.locator('.app-window').screenshot(path=str(screenshots / f'{stage}.png'))
        overflow = page.evaluate('document.documentElement.scrollWidth > innerWidth')
        assert not overflow, stage
        report['screens'].append({'stage': stage, 'viewport': [1440,1080], 'horizontal_overflow': overflow})
    page.goto(f'{base}/index.html?screen=connect')
    assert page.locator('#to-plan').is_disabled()
    page.get_by_role('button', name='Use example rig', exact=True).click()
    page.get_by_role('button', name='Check audio route', exact=True).click()
    page.wait_for_function('document.querySelector("#to-plan") && !document.querySelector("#to-plan").disabled')
    page.get_by_role('button', name='Continue to plan').click()
    assert page.get_by_role('heading', name='Choose your capture quality').is_visible()
    report['interactions'].append('setup readiness gates route check and plan')
    page.get_by_role('button', name='Start capturing').click()
    assert page.locator('#record-take').is_disabled()
    page.locator('#knobs-ready').check()
    page.get_by_role('button', name='Record this setting', exact=True).click()
    page.get_by_role('button', name='Cancel this take', exact=True).click()
    assert page.get_by_text('0 of 40', exact=True).is_visible()
    report['interactions'].append('cancelled take preserves saved count and setting')
    page.locator('#knobs-ready').check()
    page.get_by_role('button', name='Record this setting', exact=True).click()
    page.wait_for_selector('#knobs-ready', timeout=10000)
    assert page.get_by_text('1 of 40', exact=True).is_visible()
    assert not page.locator('#knobs-ready').is_checked()
    report['interactions'].append('accepted take advances one setting and clears ready confirmation')
    page.get_by_text('Try a failure or completion state').click()
    page.get_by_role('button', name='Clipped take', exact=True).click()
    assert page.get_by_text('1 of 40', exact=True).is_visible()
    page.locator('.app-window').screenshot(path=str(screenshots / 'capture-error.png'))
    report['interactions'].append('clipped take stays on same target without accepting it')
    page.get_by_role('button', name='Session complete', exact=True).click()
    page.get_by_role('button', name='Check dataset & continue').click()
    page.get_by_role('button', name='Start training', exact=True).click()
    assert page.locator('.training-chart polyline').count()==0
    assert page.get_by_text('Waiting for the first measurement',exact=True).is_visible()
    page.locator('.app-window').screenshot(path=str(screenshots / 'train-running.png'))
    page.get_by_role('button', name='Capture Record your pedal').click()
    page.get_by_role('button', name='Train Build the model').click()
    page.wait_for_selector('#to-review', timeout=10000)
    report['interactions'].append('example training continues across stage navigation and ends at review')
    page.get_by_role('button', name='Review the model').click()
    page.get_by_role('button', name='Mark example reviewed').click()
    assert page.get_by_text('Finish the listening checklist before marking this example reviewed.').is_visible()
    for check in page.locator('.review-check').all(): check.check()
    page.get_by_role('button',name='Trained model',exact=True).click()
    page.get_by_role('button',name='Preview comparison flow',exact=True).click()
    page.get_by_role('button',name='Capture Record your pedal').click()
    page.get_by_role('button',name='Review Check & export').click()
    assert all(c.is_checked() for c in page.locator('.review-check').all())
    assert page.locator('#ab-model').get_attribute('aria-pressed')=='true'
    report['interactions'].append('listening checks and A/B selection survive re-render and stage navigation')
    with page.expect_download() as download:
        page.get_by_role('button', name='Download example handoff').click()
    assert download.value.suggested_filename.endswith('.example.json')
    page.get_by_role('button', name='Mark example reviewed').click()
    assert page.get_by_role('button', name='Example reviewed', exact=True).is_disabled()
    report['interactions'].append('review requires all checks; download is labeled non-model example')
    page.goto(f'{base}/index.html?screen=train')
    page.get_by_text('Try the training error state').click()
    page.get_by_role('button', name='GPU memory error', exact=True).click()
    page.locator('.app-window').screenshot(path=str(screenshots / 'train-error.png'))
    page.get_by_role('button', name='Retry on CPU', exact=True).click()
    assert page.locator('#train-device').input_value()=='cpu'
    report['interactions'].append('GPU error has a CPU recovery action without recapture')
    page.goto(f'{base}/index.html?screen=train')
    page.get_by_role('button',name='Test run · 1 epoch',exact=True).click()
    page.get_by_role('button',name='Start training',exact=True).click()
    assert 'of 1' in page.locator('.log').inner_text()
    assert page.locator('.training-chart').get_attribute('aria-label').endswith('no real measurements')
    page.wait_for_selector('#choose-full')
    assert page.get_by_text('The example setup test passed.',exact=True).is_visible()
    assert page.locator('#to-review').count()==0
    page.locator('.app-window').screenshot(path=str(screenshots / 'train-test-passed.png'))
    page.get_by_role('button',name='Choose full training',exact=True).click()
    assert page.locator('#profile-full').get_attribute('aria-pressed')=='true'
    report['interactions'].append('quick test is successful setup state with full-training next step, not a reviewed model')
    report['interactions'].append('training chart only shows past epochs and selected preset total')
    page.goto(f'{base}/index.html?screen=plan')
    page.get_by_text('Advanced · knob settings and recording details',exact=True).click()
    page.locator('#drive-min').fill('1')
    page.locator('#drive-min').dispatch_event('change')
    assert page.evaluate('document.activeElement.id')=='drive-min'
    page.locator('#drive-max').fill('0.5')
    page.locator('#drive-max').dispatch_event('change')
    assert not page.locator('#drive-max').evaluate('el=>el.validity.valid')
    page.locator('#drive-max').fill('8')
    page.locator('#drive-max').dispatch_event('change')
    page.locator('#drive-step').select_option('1')
    page.get_by_role('button',name='Capture Record your pedal').click()
    assert page.locator('.dial-unit').first.locator('.setting').inner_text()=='5.0'
    page.get_by_role('button',name='Plan Controls & coverage').click()
    assert page.locator('#drive-min').input_value()=='1'
    assert page.locator('#drive-max').input_value()=='8'
    assert page.locator('#drive-step').input_value()=='1'
    report['interactions'].append('range/increment edits persist, change targets, retain focus and recover from invalid input')
    page.get_by_role('button',name='Connect Audio & wiring').click()
    page.get_by_text('Advanced routing and failure examples').click()
    page.locator('#buffer-choice').select_option('1024')
    page.locator('#timing-choice').select_option('return')
    assert page.locator('#to-plan').is_disabled()
    page.get_by_role('button',name='Plan Controls & coverage').click()
    page.get_by_role('button',name='Connect Audio & wiring').click()
    page.get_by_text('Advanced routing and failure examples').click()
    assert page.locator('#buffer-choice').input_value()=='1024'
    assert page.locator('#timing-choice').input_value()=='return'
    report['interactions'].append('routing edits persist and invalidate earlier route check')
    page.goto(f'{base}/index.html?screen=capture')
    page.get_by_text('Try a failure or completion state').click()
    page.get_by_role('button',name='Clipped take',exact=True).click()
    page.get_by_role('button',name='New calibrated session',exact=True).click()
    assert page.get_by_text('Start a new calibrated example session.',exact=True).is_visible()
    assert 'previous 18 example takes' in page.locator('.notice').inner_text()
    page.get_by_role('button',name='Use example rig',exact=True).click()
    page.get_by_role('button',name='Check audio route',exact=True).click()
    page.wait_for_function('!document.querySelector("#to-plan").disabled')
    page.get_by_role('button',name='Capture Record your pedal').click()
    assert page.get_by_text('0 of 40',exact=True).is_visible()
    report['interactions'].append('gain adjustment starts separate calibration with zero new takes and preserves earlier session identity')
    page.goto(f'{base}/index.html?screen=plan')
    slider=page.get_by_role('slider',name='Capture quality',exact=True)
    assert slider.input_value()=='2'
    assert 'Good, recommended' in slider.get_attribute('aria-valuetext')
    assert not page.locator('#plan-advanced').evaluate('el=>el.open')
    assert not page.locator('#train-count').is_visible()
    expectations=[(0,8,3,15,'2','Quick test'),(1,18,4,26,'1','Decent'),(2,30,6,40,'0.5','Good'),(3,54,10,68,'0.5','Thorough'),(4,96,16,116,'0.5','Overkill')]
    for level,train,test,total,step,name in expectations:
        slider.focus()
        slider.press('Home')
        for _ in range(level): slider.press('ArrowRight')
        assert slider.input_value()==str(level)
        assert page.locator('#train-count').input_value()==str(train)
        assert page.locator('#valid-count').input_value()==str(test)
        assert page.locator('#drive-step').input_value()==step
        assert page.locator('#tone-step').input_value()==step
        assert page.locator('#drive-min').input_value()=='0.5'
        assert page.locator('#tone-max').input_value()=='10'
        assert page.locator('#quality-recordings').inner_text()==f'{total} recordings'
        assert name in slider.get_attribute('aria-valuetext')
        assert page.evaluate('document.activeElement.id')=='capture-quality'
        assert page.locator('.coverage svg circle').count()==train+test
        if level in (0,4):
            page.locator('.app-window').screenshot(path=str(screenshots / f'plan-quality-{level}.png'))
    report['interactions'].append('all five quality levels jointly set recording/test counts and both knob steps while preserving physical ranges')
    report['interactions'].append('Good is recommended by default; advanced controls are collapsed; keyboard slider retains focus and reports effort')
    box=slider.bounding_box()
    page.mouse.move(box['x']+box['width']-13,box['y']+box['height']/2)
    page.mouse.down()
    page.mouse.move(box['x']+13,box['y']+box['height']/2,steps=12)
    page.mouse.up()
    assert slider.input_value()=='0'
    assert page.locator('#quality-recordings').inner_text()=='15 recordings'
    report['interactions'].append('pointer dragging keeps the slider mounted and updates the plan through multiple levels')
    page.get_by_role('button',name='Start capturing').click()
    assert page.get_by_text('0 of 15',exact=True).is_visible()
    page.locator('#knobs-ready').check()
    page.get_by_role('button',name='Record this setting',exact=True).click()
    page.wait_for_selector('#knobs-ready')
    page.get_by_role('button',name='Plan Controls & coverage').click()
    assert page.locator('#capture-quality').is_disabled()
    assert page.locator('#drive-step').is_disabled()
    page.locator('#capture-quality').evaluate("el=>{el.value='4';el.dispatchEvent(new Event('input',{bubbles:true}));}")
    assert page.locator('#quality-recordings').inner_text()=='15 recordings'
    assert page.locator('#capture-quality').input_value()=='0'
    page.locator('.app-window').screenshot(path=str(screenshots/'plan-locked.png'))
    page.get_by_role('button',name='Start a separate plan',exact=True).click()
    assert page.locator('#capture-quality').is_enabled()
    page.get_by_text('Advanced · knob settings and recording details',exact=True).click()
    assert page.get_by_text('1 of 15 takes · Quick test · kept separately',exact=True).is_visible()
    slider=page.locator('#capture-quality')
    slider.focus()
    slider.press('End')
    page.get_by_role('button',name='Start capturing').click()
    assert page.get_by_text('0 of 116',exact=True).is_visible()
    report['interactions'].append('recording locks the plan; a separate plan preserves earlier take metadata and starts at zero with new quality')
    page.goto(f'{base}/index.html?screen=plan')
    page.get_by_text('Advanced · knob settings and recording details',exact=True).click()
    page.locator('#train-count').fill('35')
    page.locator('#train-count').dispatch_event('change')
    assert page.get_by_text('Custom settings',exact=True).is_visible()
    page.locator('#capture-quality').focus()
    page.locator('#capture-quality').press('ArrowRight')
    assert page.locator('#train-count').input_value()=='54'
    assert page.get_by_text('Custom settings',exact=True).count()==0
    report['interactions'].append('manual advanced edits are marked custom; changing quality restores the complete automatic preset')
    page.locator('.app-window').screenshot(path=str(screenshots/'plan-advanced.png'))
    for width,height in [(960,900),(720,1000),(390,844)]:
        for stage in ('connect','plan','capture','train','review'):
            page.set_viewport_size({'width':width,'height':height})
            page.goto(f'{base}/index.html?screen={stage}')
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), f'{stage} at {width}'
            page.screenshot(path=str(screenshots / f'{stage}-{width}.png'), full_page=True)
            report['screens'].append({'stage':stage,'viewport':[width,height],'horizontal_overflow':False})
    page.set_viewport_size({'width':1440,'height':1080})
    page.goto(f'{base}/overview.html')
    page.screenshot(path=str(screenshots / 'overview.png'), full_page=True)
    assert not report['console_errors'],report['console_errors']
    page.goto((root/'docs/mockups/index.html').as_uri()+'?screen=capture')
    assert page.get_by_role('heading',name='Capture your pedal').is_visible()
    page.locator('#knobs-ready').check()
    assert page.locator('#record-take').is_enabled()
    report['interactions'].append('offline file URL loads complete interactive mockup without server')
    browser.close()
(root / 'docs/ui-audit/evidence/mockup-verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
