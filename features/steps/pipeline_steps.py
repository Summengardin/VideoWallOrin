# features/steps/pipeline_steps.py

from behave import given, when, then
from VisionController.libs.gst.pipeline_manager import PipelineManager

@given('a Pipeline Manager is initialized with default settings')
def step_impl(context):
    context.manager = PipelineManager()

@then('the pipeline should have {expected_count:d} active sources')
def step_impl(context, expected_count):
    assert len([source for source in context.manager.sources if source.active]) == expected_count

@then('the default configuration should be loaded correctly')
def step_impl(context):
    assert context.manager.width == 3840
    assert context.manager.height == 2160

@when('I add a source with ID {source_id:d}')
def step_impl(context, source_id):
    context.manager.add_source(source_id)

@when('I remove the source with ID {source_id:d}')
def step_impl(context, source_id):
    context.manager.remove_source(source_id)

@when('I start the pipeline')
def step_impl(context):
    context.manager.start()

@then('the pipeline should be in the playing state')
def step_impl(context):
    state = context.manager.pipeline.get_state(1).state
    assert state == 'playing'

@when('I stop the pipeline')
def step_impl(context):
    context.manager.stop()

@then('the pipeline should be stopped')
def step_impl(context):
    assert context.manager.pipeline.get_state(1).state == 'null'
