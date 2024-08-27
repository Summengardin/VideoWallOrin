# features/environment.py

def before_all(context):
    print("Setting up environment for Behave tests")

def after_all(context):
    print("Tearing down environment after Behave tests")

def before_scenario(context, scenario):
    print(f"Starting scenario: {scenario.name}")

def after_scenario(context, scenario):
    print(f"Finished scenario: {scenario.name}")
