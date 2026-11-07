import {build} from 'esbuild';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const here=path.dirname(fileURLToPath(import.meta.url));
await build({entryPoints:[path.join(here,'app.js')],bundle:true,minify:true,format:'iife',outfile:path.join(here,'app.bundle.js'),loader:{'.glsl':'text'},logLevel:'info'});
