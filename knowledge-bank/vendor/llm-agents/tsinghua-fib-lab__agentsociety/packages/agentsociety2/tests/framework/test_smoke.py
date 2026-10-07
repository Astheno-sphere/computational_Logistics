def test_import_package():
    import agentsociety2

    assert isinstance(agentsociety2.__version__, str)
    assert agentsociety2.__version__
