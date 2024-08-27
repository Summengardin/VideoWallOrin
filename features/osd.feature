Feature: OSD Manager

  Scenario: Initialize OSD Manager
    Given an OSD Manager is initialized
    Then it should have 3 default OSD text entries
    And the tiles should be initialized correctly

  Scenario: Add and Manage OSD Text
    Given an OSD Manager is initialized
    When I add a new OSD text entry
    Then the OSD Manager should have 4 OSD text entries

  Scenario: Add Timeout OSD Text
    Given an OSD Manager is initialized
    When I add a timeout OSD text entry with a 2-second timeout
    Then the OSD Manager should have 4 OSD text entries
    And after 3 seconds, the OSD Manager should have 3 OSD text entries

  Scenario: Stop the OSD Manager
    Given an OSD Manager is initialized and running
    When I stop the OSD Manager
    Then the OSD update thread should be stopped
