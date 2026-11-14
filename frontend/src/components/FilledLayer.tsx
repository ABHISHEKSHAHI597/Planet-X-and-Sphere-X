/** Display-only fitted cores: a dashed outline and a raw-science-pixel toggle. */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { ViewTransform } from "../gl/renderer";
import { gridToCanvas, fullView } from "../lib/viewport";

export function FilledLayer({viewKey,bin,band,nx,ny,transform}: {
  viewKey:string;bin:string;band:number;nx:number;ny:number;transform:ViewTransform|null;
}) {
  const [mask,setMask]=useState<Uint8Array|null>(null);
  useEffect(()=>{
    let live=true;
    // Through the API client, so the mock and ParallaX Lite answer it too (a bare fetch of /api/v1 bypassed them).
    api.filledMask(viewKey,bin,band)
      .then(b=>{if(live)setMask(b);}).catch(()=>{if(live)setMask(null);});
    return ()=>{live=false;};
  },[viewKey,bin,band]);
  if(!mask||mask.length!==nx*ny)return null;
  const v=transform??fullView(nx,ny);
  const cells=[];
  for(let row=0;row<ny;row++)for(let col=0;col<nx;col++)if(mask[row*nx+col]){
    const a=gridToCanvas(col,row,1000,1000,nx,ny,v);
    const b=gridToCanvas(col+1,row+1,1000,1000,nx,ny,v);
    cells.push(<rect key={`${row}-${col}`} x={Math.min(a.x,b.x)} y={Math.min(a.y,b.y)}
      width={Math.abs(b.x-a.x)} height={Math.abs(b.y-a.y)}/>);
  }
  return <svg className="flag-layer" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="Model-filled pixels; display only"
    style={{pointerEvents:"none",fill:"none",stroke:"white",strokeWidth:2,strokeDasharray:"6 5"}}>{cells}</svg>;
}
