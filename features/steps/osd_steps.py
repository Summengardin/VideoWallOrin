# features/steps/osd_steps.py

import time
from behave import given, when, then
from VisionController.libs.gst.osd_manager import OSDManager

@given('an OSD Manager is initialized')
def step_impl(context):
    context.manager = OSDManager()

@then('it should have {expected_count:d} default OSD text entries')
def step_impl(context, expected_count):
    assert len(context.manager.osd_text_dicts) == expected_count

@then('the tiles should be initialized correctly')
def step_impl(context):
    for tile in context.manager.tiles:
        assert len(tile) == 3
    assert context.manager.tiles[0][2]['text'] == 'LOWER RIGHT'

@when('I add a new OSD text entry')
def step_impl(context):
    context.manager.add_text(0, "New Text", 0, 0, 18, (1.0, 1.0, 1.0, 1.0), (0.0, 0.0, 0.0, 0.6))

@then('the OSD Manager should have {expected_count:d} OSD text entries')
def step_impl(context, expected_count):
    assert len(context.manager.osd_text_dicts) == expected_count

@when('I add a timeout OSD text entry with a {timeout:d}-second timeout')
def step_impl(context, timeout):
    context.manager.add_timeout_text(0, "Timeout Text", 0, 0, 18, (1.0, 1.0, 1.0, 1.0), (0.0, 0.0, 0.0, 0.6), timeout)

@then('after {wait_time:d} seconds, the OSD Manager should have {expected_count:d} OSD text entries')
def step_impl(context, wait_time, expected_count):
    time.sleep(wait_time)
    context.manager._update_texts()  # Manually trigger the update to simulate the passage of time
    assert len(context.manager.osd_text_dicts) == expected_count

@when('I stop the OSD Manager')
def step_impl(context):
    context.manager.stop()

@then('the OSD update thread should be stopped')
def step_impl(context):
    assert not context.manager.update_thread.is_alive()
