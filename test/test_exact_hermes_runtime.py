"""Opt-in exact-source + OpenAI 2.24.0 loop test, with a local synthetic endpoint only."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from hermes_profile import write_profile, session_environment, PROVIDER

SOURCE=os.environ.get('HERMES_TEST_SOURCE')


@unittest.skipUnless(SOURCE,'Set HERMES_TEST_SOURCE to the exact Hermes checkout')
class ExactHermesRuntimeTests(unittest.TestCase):
    def test_real_hermes_resolution_and_sdk_streaming_tool_roundtrip(self):
        sys.path.insert(0,str(Path(SOURCE).resolve()))
        import openai
        import httpx
        self.assertEqual(openai.__version__,'2.24.0')
        requests=[];errors=[];reject_receipt=False
        testcase=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                nonlocal reject_receipt
                try:
                    body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    testcase.assertEqual(self.path,'/v1/chat/completions')
                    testcase.assertEqual(self.headers['Authorization'],'Bearer fixture-session-token')
                    testcase.assertEqual(body['model'],'lordx64/cyberglm')
                    requests.append(body)
                    self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
                    if reject_receipt:
                        self.wfile.write(b'event: error\ndata: {"error":{"type":"confidential_gateway_error","message":"confidential stream ended without a verified receipt"}}\n\n');return
                    def send(delta,finish=None):
                        value={'id':'fixture','object':'chat.completion.chunk','created':1,'model':body['model'],'choices':[{'index':0,'delta':delta,'finish_reason':finish}]}
                        self.wfile.write(('data: '+json.dumps(value)+'\n\n').encode())
                    if any(m['role']=='tool' for m in body['messages']):
                        testcase.assertEqual(body['messages'][-1]['content'],'local-fixture-value')
                        send({'role':'assistant','content':'HERMES_CONFIDENTIAL_OK'});send({},'stop')
                    else:
                        send({'role':'assistant','tool_calls':[{'index':0,'id':'call_fixture','type':'function','function':{'name':'echo_fixture','arguments':'{"value":'}}]})
                        send({'tool_calls':[{'index':0,'function':{'arguments':'"local-fixture-value"}'}}]});send({},'tool_calls')
                    self.wfile.write(b'data: [DONE]\n\n')
                except Exception as error:
                    errors.append(str(error));raise
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        url=f'http://127.0.0.1:{server.server_port}/v1'
        try:
            with tempfile.TemporaryDirectory() as temp:
                home=Path(temp)/'profiles'/'adverserial'
                write_profile(home,'lordx64/cyberglm',url)
                env=session_environment({'PATH':os.environ.get('PATH',''),'HOME':temp,'ADVERSERIAL_API_KEY':'fixture-session-token','ADVERSERIAL_GATEWAY_URL':url},home)
                with patch.dict(os.environ,env,clear=True):
                    from hermes_cli.runtime_provider import resolve_runtime_provider
                    runtime=resolve_runtime_provider(requested=PROVIDER,target_model='lordx64/cyberglm')
                    self.assertEqual(runtime['base_url'],url)
                    self.assertEqual(runtime['api_key'],'fixture-session-token')
                    self.assertEqual(runtime['api_mode'],'chat_completions')
                    with openai.OpenAI(api_key=runtime['api_key'],base_url=runtime['base_url'],http_client=httpx.Client(trust_env=False),max_retries=0) as client:
                        messages=[{'role':'user','content':'Local fixture only.'}]
                        tools=[{'type':'function','function':{'name':'echo_fixture','parameters':{'type':'object','properties':{'value':{'type':'string'}},'required':['value']}}}]
                        fragments=''
                        with client.chat.completions.create(model='lordx64/cyberglm',messages=messages,tools=tools,stream=True) as stream:
                            for part in stream:
                                for call in part.choices[0].delta.tool_calls or []:fragments+=call.function.arguments or ''
                        tool=json.loads(fragments)
                        messages += [{'role':'assistant','tool_calls':[{'id':'call_fixture','type':'function','function':{'name':'echo_fixture','arguments':fragments}}]}, {'role':'tool','tool_call_id':'call_fixture','content':tool['value']}]
                        response=''
                        with client.chat.completions.create(model='lordx64/cyberglm',messages=messages,tools=tools,stream=True) as stream:
                            for part in stream:response+=part.choices[0].delta.content or ''
                        self.assertEqual(response,'HERMES_CONFIDENTIAL_OK')
                        reject_receipt=True
                        with self.assertRaises(openai.APIError):
                            with client.chat.completions.create(model='lordx64/cyberglm',messages=messages,stream=True) as stream:list(stream)
                self.assertEqual(len(requests),3)
                self.assertEqual(errors,[])
                text=(home/'config.yaml').read_text()
                self.assertNotIn('fixture-session-token',text)
        finally:
            server.shutdown();server.server_close();worker.join(timeout=2)


if __name__=='__main__':unittest.main()
