"""Local UI protocol fixture: no model loading or quality evaluation."""
import json
import time
from jev.server import make_server
from jev.serving import Predictor


class FixtureScorer:
    def score(self, records):
        return [[0.0, 1.0] if record['kind'] == 'noul' else
                [-float(index) for index in range(len(record['options']))]
                for record in records], 0


class FixturePredictor(Predictor):
    def predict(self, request):
        state = request.get('state') if isinstance(request, dict) else None
        if isinstance(state, dict) and state.get('image_description') == 'SLOW PROTOCOL FIXTURE':
            time.sleep(0.5)
        return super().predict(request)


predictor = FixturePredictor(
    FixtureScorer(), model_name='PROTOCOL_FIXTURE_NO_MODEL',
    method='LOCAL_CPU_UI_SMOKE_FIXTURE', provenance={'fixture_only': True})
server = make_server(predictor, host='127.0.0.1', port=55035)
print(json.dumps({'url': 'http://127.0.0.1:55035', 'fixture_only': True}), flush=True)
try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    server.server_close()
