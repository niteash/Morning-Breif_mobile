import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';
async function load(path) {
  const { outputText } = ts.transpileModule(await readFile(new URL(path, import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
}
const { parsePreferences, createPreferences } = await load('../src/lib/preferences.ts');
const { english, translate } = await load('../src/theme/copy.ts');
const { parseTrial } = await load('../src/lib/entitlement.ts');
test('unknown or corrupt device preferences fall back safely', () => {
  for (const input of ['broken','null','{"language":"de","theme":"unknown"}']) assert.deepEqual(parsePreferences(input),{language:'my',theme:'light'});
  assert.deepEqual(parsePreferences('{"language":"en","theme":"dark"}'),{language:'en',theme:'dark'});
});
test('late storage hydration never overrides a new user choice; writes stay ordered', async () => {
  let resolve; const writes=[];
  const prefs=createPreferences({getItem:()=>new Promise(r=>resolve=r),setItem:async(k,v)=>writes.push(JSON.parse(v))});
  const hydration=prefs.hydrate();
  const first=prefs.set({language:'en'}),second=prefs.set({theme:'dark'});
  resolve('{"language":"my","theme":"light"}');
  await Promise.all([hydration,first,second]);
  assert.equal(prefs.getSnapshot().theme,'dark');assert.equal(prefs.getSnapshot().language,'en');
  assert.equal(writes[1].theme,'dark');
});
test('failed preference persistence is visible and recoverable', async () => {
  let fail=true;
  const prefs=createPreferences({getItem:async()=>null,setItem:async()=>{if(fail)throw Error();}});
  await prefs.set({theme:'dark'});assert.equal(prefs.getSnapshot().error,true);
  fail=false;await prefs.set({theme:'dark'});assert.equal(prefs.getSnapshot().error,false);
});
test('application copy translates both ways without inventing server content', () => {
  for(const [my,en] of Object.entries(english)) {
    assert.equal(translate(my,'en'),en);assert.equal(translate(my,'my'),my);
  }
  assert.equal(translate('Publisher headline not in the app dictionary','en'),'Publisher headline not in the app dictionary');
});
test('entitlement presentation rejects malformed or contradictory grants', () => {
  const denied={status:'claim_required',expires_at:null,can_generate:false,claim_mode:'device_required'};
  assert.deepEqual(parseTrial(denied),denied);
  for(const value of [null,{}, {...denied,can_generate:true},{...denied,can_generate:'true'},{...denied,status:'unknown'}]) assert.throws(()=>parseTrial(value));
  assert.equal(parseTrial({...denied,status:'trial_active',expires_at:'2026-12-01T00:00:00Z',can_generate:true}).can_generate,true);
  assert.equal(parseTrial({...denied,status:'subscription_active',can_generate:true}).can_generate,true);
});
