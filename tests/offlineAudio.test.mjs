import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';
const {outputText}=ts.transpileModule(await readFile(new URL('../src/lib/offlineAudio.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {createOfflineAudio,offlineKey}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const record={id:'11111111-1111-4111-8111-111111111111',user_id:'owner',generated_at:'2026-11-14T00:00:00Z',briefing_date:'2026-11-14',status:'ready',audio_url:'https://storage.invalid/signed?secret=never-save',script:'Burmese',duration_seconds:60};
function setup(){
 let manifest=[],files=new Set();
 const port={read:async()=>structuredClone(manifest),write:async v=>{manifest=structuredClone(v);},download:async(url,key)=>{files.add(key);},exists:async key=>files.has(key),uri:key=>'file://private/'+key,remove:async key=>{files.delete(key);},cancel:async()=>{},clear:async()=>{files.clear();manifest=[];}};
 return {port,cache:createOfflineAudio('owner',port,()=>1000),manifest:()=>manifest,files};
}
test('downloads store no signed URLs and cannot cross accounts',async()=>{
 const {cache,manifest}=setup();await cache.list();await cache.save(record);
 assert.equal(JSON.stringify(manifest()).includes('secret'),false);
 assert.equal((await cache.open(record.id)).offline,true);
 await assert.rejects(cache.save({...record,user_id:'other'}));
 assert.throws(()=>offlineKey({...record,id:'../../private'}));
});
test('incomplete downloads never appear as saved',async()=>{
 const {cache,port,manifest,files}=setup();port.download=async()=>{throw Error('network');};
 await assert.rejects(cache.save(record));assert.deepEqual(manifest(),[]);assert.equal(files.size,0);
});
test('logout waits for in-flight cleanup and late completion cannot restore downloads',async()=>{
 const {cache,port,files,manifest}=setup();let complete;
 port.download=async(url,key)=>{await new Promise(r=>complete=r);files.add(key);};
 const save=cache.save(record);await Promise.resolve();
 const clear=cache.clear();complete();
 await assert.rejects(save);await clear;
 assert.deepEqual(manifest(),[]);assert.equal(files.size,0);await assert.rejects(cache.open(record.id));
});
test('repeated download is idempotent; missing local files are not playable',async()=>{
 const {cache,port,files}=setup();let calls=0;const download=port.download;port.download=async(...args)=>{calls++;await download(...args);};
 await cache.save(record);await cache.save(record);assert.equal(calls,1);
 files.clear();await assert.rejects(cache.open(record.id));assert.deepEqual(await cache.list(),[]);
});
test('foreign and expired manifest records never become playable',async()=>{
 const {cache,port}=setup();port.exists=async()=>true;
 port.read=async()=>[{...record,key:offlineKey(record),user_id:'other',saved_at:500},{...record,key:offlineKey(record),saved_at:-8*86400_000}];
 assert.deepEqual(await cache.list(),[]);await assert.rejects(cache.open(record.id));
});
