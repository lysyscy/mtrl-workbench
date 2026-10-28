import type { IDragAndDropImageParams } from 'ag-grid-community';

// AG Grid owns dragging and positioning; this public image component preserves
// the existing whole-row preview without maintaining another drag controller.
export class ProjectDragImage {
  private element=document.createElement('div');
  init(params:IDragAndDropImageParams){
    const row=params.dragSource.eElement.closest<HTMLElement>('.ag-row');
    if(!row)return;
    const source=row.closest<HTMLElement>('.ag-root-wrapper'),copy=row.cloneNode(true) as HTMLElement,box=row.getBoundingClientRect();
    this.element.className=(source?.className??'')+' business-grid project-drag-image';
    this.element.setAttribute('aria-hidden','true');
    Object.assign(this.element.style,{width:box.width+'px',height:box.height+'px',maxWidth:'90vw',overflow:'hidden',pointerEvents:'none'});
    Object.assign(copy.style,{position:'relative',top:'0',left:'0',transform:'none',width:box.width+'px',height:box.height+'px'});
    copy.removeAttribute('id');
    for(const node of copy.querySelectorAll('[id]'))node.removeAttribute('id');
    for(const node of copy.querySelectorAll<HTMLElement>('input,button,select,textarea,[tabindex]'))node.tabIndex=-1;
    this.element.append(copy);
  }
  getGui(){return this.element;}
  setIcon(_icon:unknown,_shake:boolean){}
  setLabel(_label:string){}
}
