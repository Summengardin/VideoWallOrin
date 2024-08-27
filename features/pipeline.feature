Feature: Pipeline Manager

  Scenario: Initialize Pipeline Manager
    Given a Pipeline Manager is initialized with default settings
    Then the pipeline should have 0 active sources
    And the default configuration should be loaded correctly

  Scenario: Add and Remove Sources
    Given a Pipeline Manager is initialized with default settings
    When I add a source with ID 0
    Then the pipeline should have 1 active source
    When I remove the source with ID 0
    Then the pipeline should have 0 active sources

  Scenario: Start and Stop the Pipeline
    Given a Pipeline Manager is initialized with default settings
    When I start the pipeline
    Then the pipeline should be in the playing state
    When I stop the pipeline
    Then the pipeline should be stopped
