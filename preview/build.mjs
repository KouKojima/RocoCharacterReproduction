import {build} from 'esbuild';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const here=path.dirname(fileURLToPath(import.meta.url));
// GLSL is inlined as text. Normalize CRLF so a Windows checkout produces the
// exact same bundle bytes as an LF checkout (see docs/04).
const glslEol={name:'glsl-eol',setup(b){
 b.onLoad({filter:/\.glsl$/},async args=>({contents:(await readFile(args.path,'utf8')).replace(/\r\n/g,'\n'),loader:'text'}));
}};
await build({entryPoints:[path.join(here,'app.js')],bundle:true,minify:true,format:'iife',outfile:path.join(here,'app.bundle.js'),loader:{'.glsl':'text'},plugins:[glslEol],logLevel:'info'});
