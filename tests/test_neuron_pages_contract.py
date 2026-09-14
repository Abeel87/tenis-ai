from pathlib import Path


def test_neuron_workflow_publishes_pages_after_artifacts():
    text = Path('.github/workflows/neuron-shadow.yml').read_text(encoding='utf-8')
    assert 'pages: write' in text
    assert 'id-token: write' in text
    assert 'deploy-neuron-ui:' in text
    assert 'needs: neuron' in text
    assert 'ref: main' in text
    assert 'actions/upload-pages-artifact@v4' in text
    assert 'actions/deploy-pages@v4' in text
    assert 'path: frontend' in text
