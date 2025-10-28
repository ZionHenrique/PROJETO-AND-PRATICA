async function exportCSV(){
  const res = await fetch('/api/entries'); const rows = await res.json();
  let csv = 'Data,Matéria,Horas,Qualidade,Dificuldade,Nota\n';
  rows.forEach(r=> csv += `${r.date},${r.subject_name},${r.hours},${r.quality},${r.difficulty},${r.grade ?? ''}\n`);
  const blob = new Blob([csv],{type:'text/csv'}); const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = 'estudos_export.csv'; a.click(); URL.revokeObjectURL(url);
}
document.getElementById('btn-export').onclick = exportCSV;
