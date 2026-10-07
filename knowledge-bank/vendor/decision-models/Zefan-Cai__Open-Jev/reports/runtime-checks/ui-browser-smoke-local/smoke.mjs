import fs from 'node:fs/promises';
const scratch='/var/folders/j_/cgptvvk145zdy4jv1wfk5j8r0000gn/T/open-jev-ui-smoke-z9qwsrip';
const config=JSON.parse(await fs.readFile(scratch+'/browser-session.json','utf8'));
const phase=process.argv[2]||'before';
const tab=await (await fetch(`http://127.0.0.1:${config.port}/json/new?about:blank`,{method:'PUT'})).json();
const socket=new WebSocket(tab.webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
let sequence=0;const pending=new Map(),requests=[],exceptions=[];
socket.onmessage=event=>{const message=JSON.parse(event.data);if(message.id){const p=pending.get(message.id);pending.delete(message.id);if(message.error)p.reject(Error(JSON.stringify(message.error)));else p.resolve(message.result);}else if(message.method==='Network.requestWillBeSent'&&message.params.request.method==='POST'){requests.push({url:message.params.request.url,body:JSON.parse(message.params.request.postData||'{}')});}else if(message.method==='Runtime.exceptionThrown'){exceptions.push(message.params.exceptionDetails.text);}};
const cdp=(method,params={})=>new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});
const js=async expression=>{const value=await cdp('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(value.exceptionDetails)throw Error(JSON.stringify(value.exceptionDetails));return value.result.value;};
async function wait(expression){const end=Date.now()+12000;while(Date.now()<end){if(await js(expression))return;await new Promise(resolve=>setTimeout(resolve,40));}throw Error('Timeout: '+expression);}
const navigate=async(path,ready)=>{await cdp('Page.navigate',{url:config.fixture_url+path});await wait(ready);};
await cdp('Page.enable');await cdp('Runtime.enable');await cdp('Network.enable');await cdp('Emulation.setDeviceMetricsOverride',{width:1280,height:1000,deviceScaleFactor:1,mobile:false});
const report={phase,fixture_only:true,model_accuracy_evaluated:false,fixture_url:config.fixture_url,browser:(await cdp('Browser.getVersion')).product,checks:[]};
try{
 await navigate('/',`document.getElementById('request')?.value.length>0 && document.getElementById('health')?.textContent.includes('PROTOCOL_FIXTURE_NO_MODEL')`);
 report.task_lab_initial=await js(`({health:document.getElementById('health').textContent,optionValues:Array.from(document.getElementById('examples').options).map(o=>o.value),textareaHasRequest:!!JSON.parse(document.getElementById('request').value).questions})`);
 await js(`document.getElementById('run').click()`);await wait(`!document.getElementById('run').disabled && document.getElementById('timing').textContent.includes('candidate sequences')`);
 report.task_lab_valid=await js(`({answers:document.querySelectorAll('.answer').length,error:document.getElementById('error').textContent,timing:document.getElementById('timing').textContent,model:JSON.parse(document.getElementById('raw').textContent).model})`);
 report.checks.push('initial task loads; valid request renders fixture answers');
 const artifacts=['painting/reference.json','games/trex-state.json','games/mario-state.json','games/baseline-smoke-report.json','games/wiki-graph.json'];report.non_request_menu_items=[];
 for(const path of artifacts){const present=await js(`Array.from(document.getElementById('examples').options).some(o=>o.value===${JSON.stringify(path)})`);const item={path,present};if(present){await js(`(async()=>{document.getElementById('examples').value=${JSON.stringify(path)};await document.getElementById('examples').onchange();})()`);await js(`document.getElementById('run').click()`);await wait(`!document.getElementById('run').disabled && document.getElementById('error').textContent.length>0`);item.error=await js(`document.getElementById('error').textContent`);}report.non_request_menu_items.push(item);}
 await js(`document.getElementById('request').value='{';document.getElementById('run').click()`);await wait(`!document.getElementById('run').disabled && document.getElementById('error').textContent.length>0`);report.invalid_json_message=await js(`document.getElementById('error').textContent`);
 report.checks.push('invalid JSON error visible and evaluate button re-enabled');
 const taskShot=await cdp('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await fs.writeFile(scratch+`/${phase}-task-lab.png`,Buffer.from(taskShot.data,'base64'));
 await navigate('/examples/painting/index.html',`document.getElementById('reference') && !document.getElementById('reference').disabled`);
 report.painting_reference=[];
 for(const mode of ['silhouette','palette','rgb','hsl']){const count=requests.length;await js(`document.getElementById('mode').value=${JSON.stringify(mode)};document.getElementById('reference').click()`);report.painting_reference.push(await js(`({mode:${JSON.stringify(mode)},source:document.getElementById('source').textContent,status:document.getElementById('status').textContent,size:document.getElementById('canvas').width,pixel:Array.from(document.getElementById('canvas').getContext('2d').getImageData(0,0,1,1).data)})`));if(requests.length!==count)throw Error('Reference emitted inference request');}
 report.checks.push('all four procedural representations render without inference requests');
 report.painting_fixture=[];
 for(const mode of ['silhouette','palette','rgb','hsl']){const count=requests.length;await js(`document.getElementById('mode').value=${JSON.stringify(mode)};document.getElementById('size').value='8';document.getElementById('prompt').value='PROTOCOL FIXTURE ONLY';document.getElementById('run').click()`);await wait(`!document.getElementById('run').disabled && document.getElementById('source').textContent==='MODEL PREDICTION'`);report.painting_fixture.push({mode,requests:requests.length-count,...await js(`({status:document.getElementById('status').textContent,size:document.getElementById('canvas').width,pixel:Array.from(document.getElementById('canvas').getContext('2d').getImageData(0,0,1,1).data)})`)});}
 report.checks.push('all four painting request forms accepted and fixture pixels rendered');
 const count=requests.length;await js(`document.getElementById('mode').value='rgb';document.getElementById('prompt').value='SLOW PROTOCOL FIXTURE';document.getElementById('endpoint').value=${JSON.stringify(config.fixture_url+'/v1/systemone')};document.getElementById('run').click()`);
 const end=Date.now()+5000;while(requests.length===count&&Date.now()<end)await new Promise(resolve=>setTimeout(resolve,20));if(requests.length===count)throw Error('First painting batch not observed');
 await js(`document.getElementById('endpoint').value=${JSON.stringify(config.fixture_url+'/v1/inference')}`);await wait(`!document.getElementById('run').disabled && document.getElementById('source').textContent==='MODEL PREDICTION'`);
 report.endpoint_change_during_run={post_urls:requests.slice(count).map(r=>r.url),status:await js(`document.getElementById('status').textContent`)};
 const paintShot=await cdp('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await fs.writeFile(scratch+`/${phase}-painting.png`,Buffer.from(paintShot.data,'base64'));
 await js(`document.getElementById('endpoint').value=${JSON.stringify(config.fixture_url+'/missing-endpoint')};document.getElementById('prompt').value='PROTOCOL FIXTURE ONLY';document.getElementById('run').click()`);await wait(`!document.getElementById('run').disabled && document.getElementById('source').textContent==='NO NEW MODEL RESULT'`);report.painting_http_error=await js(`({source:document.getElementById('source').textContent,status:document.getElementById('status').textContent,runEnabled:!document.getElementById('run').disabled})`);report.checks.push('painting HTTP error visible with no new result label');
 report.uncaught_browser_exceptions=exceptions;report.status='completed';
}catch(error){report.status='failed';report.error=String(error);throw error;}
finally{await fs.writeFile(scratch+`/${phase}-results.json`,JSON.stringify(report,null,2)+'\n');socket.close();await fetch(`http://127.0.0.1:${config.port}/json/close/${tab.id}`);console.log(JSON.stringify(report,null,2));}
