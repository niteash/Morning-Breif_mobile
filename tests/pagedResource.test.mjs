import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';
const source = await readFile(new URL('../src/lib/pagedResource.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
const { createPagedResource } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
test('pagination deduplicates and retry preserves offset after failure', async () => {
 let fail=true;const calls=[];
 const r=createPagedResource(async offset=>{calls.push(offset);if(offset && fail){fail=false;throw Error();}return offset?{items:[{id:'a'},{id:'b'}],next_offset:null}:{items:[{id:'a'}],next_offset:20};},x=>x.id);
 await r.refresh();await r.more();assert.equal(r.getSnapshot().items.length,1);await r.more();assert.deepEqual(calls,[0,20,20]);assert.equal(r.getSnapshot().items.length,2);
});
test('late responses cannot overwrite a new search or disposed account', async () => {
 const resolves=[];const r=createPagedResource(()=>new Promise(resolve=>resolves.push(resolve)),x=>x.id);
 const old=r.refresh(),fresh=r.refresh();resolves[1]({items:[{id:'new'}],next_offset:null});await fresh;resolves[0]({items:[{id:'old'}],next_offset:null});await old;assert.equal(r.getSnapshot().items[0].id,'new');
 const late=r.refresh();r.dispose();resolves[2]({items:[{id:'foreign'}],next_offset:null});await late;assert.equal(r.getSnapshot().items[0].id,'new');
});
