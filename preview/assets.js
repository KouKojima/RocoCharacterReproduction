import * as THREE from 'three';
let inlineFiles;
export async function loadAsset(path,json=false){
  if(window.__CHARACTER_ARCHIVE){
    if(!inlineFiles)inlineFiles=(async()=>{
      const {data,files}=window.__CHARACTER_ARCHIVE;
      const bin=atob(data),u8=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)u8[i]=bin.charCodeAt(i);
      const bytes=new Uint8Array(await new Response(new Blob([u8]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer());
      return {bytes,files};
    })();
    const archive=await inlineFiles,entry=archive.files[path];if(!entry)throw Error('Missing bundled asset '+path);
    const bytes=archive.bytes.slice(entry[0],entry[0]+entry[1]);return json?JSON.parse(new TextDecoder().decode(bytes)):bytes.buffer;
  }
  const response=await fetch(path);if(!response.ok)throw Error(path+' HTTP '+response.status);
  return json?response.json():response.arrayBuffer();
}
export async function loadTextures(root='assets/'){
  const manifest=await loadAsset(root+'textures.json',true);const result={};
  await Promise.all(manifest.map(async m=>{
    const buffer=await loadAsset(root+m.file),mips=m.mips.map(x=>({data:new Uint8Array(buffer,x.offset,x.length),width:x.width,height:x.height}));
    const texture=new THREE.DataTexture(mips[0].data,m.width,m.height,THREE.RGBAFormat,THREE.UnsignedByteType);
    texture.name=m.name;texture.mipmaps=mips;texture.generateMipmaps=false;texture.flipY=false;
    texture.colorSpace=m.srgb?THREE.SRGBColorSpace:THREE.NoColorSpace;
    texture.minFilter=mips.length>1?THREE.LinearMipmapLinearFilter:THREE.LinearFilter;texture.magFilter=THREE.LinearFilter;
    texture.wrapS=texture.wrapT=THREE.RepeatWrapping;
    if(m.name.includes('Es_D')||m.name.includes('Outline_Hue')||m.name.includes('MaskTex01'))texture.wrapS=texture.wrapT=THREE.ClampToEdgeWrapping;
    texture.needsUpdate=true;texture.userData.native=m;result[m.name]=texture;
  }));return result;
}
export async function loadMorph(root='assets/'){
 // Blend shapes are optional: a character without an extracted morph set
 // simply has no face deformation, so a missing folder is not an error.
 try{
  const [targets,curves,buffer]=await Promise.all([loadAsset(root+'morph/targets.json',true),loadAsset(root+'morph/curves.json',true),loadAsset(root+'morph/deltas.bin')]);
  return {targets,curves,buffer};
 }catch(error){return null;}
}
export async function loadModel(root='assets/'){
  const [buffer,metadata]=await Promise.all([loadAsset(root+'character.bin'),loadAsset(root+'character.json',true)]);
  const head=new Uint32Array(buffer,0,4),[magic,nv,ni,nu]=head;if(magic!==0x4343524e)throw Error('模型数据头不正确');let offset=16;
  const take=(count,Type=Float32Array)=>{const v=new Type(buffer,offset,count);offset+=count*Type.BYTES_PER_ELEMENT;return v;};
  const positions=take(nv*3),normals=take(nv*3),tangents=take(nv*4),uvs=[];for(let i=0;i<nu;i++)uvs.push(take(nv*2));
  const colors=take(nv*4,Uint8Array),originalIndices=take(ni,Uint32Array),indices=new Uint32Array(originalIndices);
  // Native UE indices are clockwise, OpenGL front faces are counter-clockwise.
  for(let i=0;i<indices.length;i+=3){const x=indices[i+1];indices[i+1]=indices[i+2];indices[i+2]=x;}
  const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(positions,3));geometry.setAttribute('normal',new THREE.BufferAttribute(normals,3));geometry.setAttribute('tangent',new THREE.BufferAttribute(tangents,4));geometry.setAttribute('uv',new THREE.BufferAttribute(uvs[0],2));geometry.setAttribute('uv1',new THREE.BufferAttribute(uvs[1]??new Float32Array(nv*2),2));geometry.setAttribute('color',new THREE.BufferAttribute(colors,4,true));geometry.setIndex(new THREE.BufferAttribute(indices,1));geometry.computeBoundingBox();geometry.computeBoundingSphere();
  return {geometry,metadata,originalIndices,raw:{positions,normals,tangents,uvs,colors}};
}
