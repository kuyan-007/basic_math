// Independently trace every occupied cell and solve the published boards.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
const read = name => readFileSync(new URL('../arrows/' + name, import.meta.url), 'utf8');
const levels = runInNewContext(read('levels.js') + read('extra-levels.js') + ';LEVELS');
assert.equal(levels.length,50);
const seen = new Set();
let quadrants = 0, total = 0;
for (const [index, level] of levels.entries()) {
  const {cols,rows,arrows,split} = level;
  const owners = new Map();
  const zone = ([x,y]) => split ? Number(x >= split[0]) + 2 * Number(y >= split[1]) : 0;
  const zones = arrows.map(path => zone(path[0]));
  const key = JSON.stringify([cols,rows,arrows.map(p => JSON.stringify(p)).sort()]);
  assert.ok(!seen.has(key),'duplicate level ' + (index+1));
  seen.add(key);
  total += arrows.length;
  arrows.forEach((path,id) => {
    assert.ok(path.length >= 2);
    let [x,y] = path[0];
    function occupy() {
      assert.ok(Number.isInteger(x) && Number.isInteger(y) && x>=0 && y>=0 && x<cols && y<rows);
      assert.equal(zone([x,y]),zones[id]);
      assert.ok(!owners.has(y*cols+x),'overlapping line');
      owners.set(y*cols+x,id);
    }
    occupy();
    for(const [tx,ty] of path.slice(1)) {
      assert.ok((tx===x)!==(ty===y),'non-orthogonal segment');
      const dx=Math.sign(tx-x), dy=Math.sign(ty-y);
      while(x!==tx || y!==ty){ x+=dx; y+=dy; occupy(); }
    }
  });
  const linked = new Set();
  const deps = arrows.map((path,id) => {
    let [x,y] = path.at(-1);
    const [a,b] = path.at(-2), dx=Math.sign(x-a), dy=Math.sign(y-b);
    const blockers=new Set();
    for(x+=dx,y+=dy;x>=0 && y>=0 && x<cols && y<rows;x+=dx,y+=dy) {
      const other=owners.get(y*cols+x);
      if(other===undefined)continue;
      assert.notEqual(other,id,'arrow faces itself');
      blockers.add(other);
      if(zones[id]!==zones[other]){ linked.add(zones[id]); linked.add(zones[other]); }
    }
    return blockers;
  });
  if(split){ quadrants++; assert.equal(linked.size,4,'isolated quadrant'); }
  const removed=new Set();
  while(removed.size<arrows.length){
    const count=removed.size;
    deps.forEach((blockers,id)=>{if([...blockers].every(b=>removed.has(b)))removed.add(id)});
    assert.ok(removed.size>count,'deadlock at level '+(index+1));
  }
}
console.log(`${levels.length} unique solvable levels; ${quadrants} four-quadrant boards; ${total} arrows`);
