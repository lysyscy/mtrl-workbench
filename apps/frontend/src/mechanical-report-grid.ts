import type { ReportSheet } from './mechanical-api';

export interface ReportDisplayRow { id:string; project:string; sourceRow:number; values:Record<string,string>; total:boolean }

// Read the server's frozen preview values. Expanding a project label for a grid
// does not recalculate a subtotal or fetch a second, newer business snapshot.
export function reportGrid(sheet:ReportSheet,index:number) {
  const head=index===0?5:index===3?1:4;
  const width=Math.max(0,...sheet.rows.flatMap(row=>row.map(cell=>cell.column+cell.colspan-1)));
  const headerRows=sheet.rows.slice(index===0?3:index===3?0:2,head);
  const titles=Array.from({length:width},(_,i)=>{
    const path=headerRows.flatMap(row=>row.filter(cell=>cell.column<=i+1&&cell.column+cell.colspan>i+1).map(cell=>cell.value.trim())).filter(Boolean);
    return [...new Set(path)];
  });
  const ids=titles.map((path,i)=>{
    const month=/^(\d{4})年(\d{1,2})月$/.exec(path.at(-1)??'');
    return index===3?(month?`month:${month[1]}-${month[2]!.padStart(2,'0')}`:i===0?'project':i===1?'category':`total:${path.join(':')}`):`c${i+1}`;
  });
  const projects=new Map(sheet.project_rows.map(project=>[project.row,project.warehouse]));
  const carried=new Map<number,{end:number;value:string}>();
  let project='';
  const rows:ReportDisplayRow[]=sheet.rows.slice(head).map((cells,offset)=>{
    const sourceRow=head+offset+1,values:Record<string,string>={};
    project=projects.get(sourceRow)??project;
    for(const [column,span] of carried)if(sourceRow<=span.end)values[ids[column-1]!]=span.value;
    for(const cell of cells){
      values[ids[cell.column-1]!]=cell.value;
      if(cell.rowspan>1)carried.set(cell.column,{end:sourceRow+cell.rowspan-1,value:cell.value});
    }
    const total=sourceRow===sheet.rows.length;
    return {id:`${sheet.name}:${sourceRow}`,project:total?'':project,sourceRow,values,total};
  });
  // Formatting roles follow the existing four template mappings; values stay frozen.
  const numeric=(column:number)=>index===0?column>=5&&column<=14:index===3?column>=3:(index===1?[5,6,7,9]:[5,6,7,8,15]).includes(column);
  return {rows,columns:ids.map((id,i)=>({id,path:titles[i]!,column:i+1,numeric:numeric(i+1)})).filter(column=>column.path.length||rows.some(row=>Boolean(row.values[column.id]?.trim())))};
}
