function makeRevenueChart(id, labels, values) {
  const el = document.getElementById(id); if (!el) return;
  new Chart(el, {type:'line',data:{labels,datasets:[{label:'Revenue (₹)',data:values,borderColor:'#6877e8',backgroundColor:'rgba(104,119,232,.12)',fill:true,tension:.38,pointRadius:2,pointHoverRadius:5,borderWidth:2}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{display:false},ticks:{maxTicksLimit:7,color:'#9aa3b6'}},y:{beginAtZero:true,grid:{color:'#f0f2f7'},ticks:{color:'#9aa3b6'}}}}});
}
function makeDoughnutChart(id, labels, values) {
  const el=document.getElementById(id); if(!el)return;
  new Chart(el,{type:'doughnut',data:{labels,datasets:[{data:values,backgroundColor:['#6877e8','#36b7a5','#f0ad62','#9b75e5','#5fa5e9','#e77f9b'],borderWidth:3,borderColor:'#fff'}]},options:{responsive:true,maintainAspectRatio:false,cutout:'68%',plugins:{legend:{position:'bottom',labels:{usePointStyle:true,boxWidth:7,padding:15,color:'#8791a8',font:{size:10}}}}}});
}
function makeForecastChart(id, actualDates, actual, forecastDates, forecast) {
  const el=document.getElementById(id); if(!el)return;
  const labels=[...actualDates,...forecastDates];
  const actualData=[...Array(Math.max(0,actualDates.length-actual.length)).fill(null),...actual,...Array(forecast.length).fill(null)];
  const forecastData=[...Array(Math.max(0,actualDates.length-1)).fill(null),actual.length?actual[actual.length-1]:null,...forecast];
  new Chart(el,{type:'line',data:{labels,datasets:[{label:'Actual units',data:actualData,borderColor:'#6675e5',backgroundColor:'#6675e5',tension:.3,pointRadius:1,borderWidth:2},{label:'Forecast units',data:forecastData,borderColor:'#27b49d',backgroundColor:'rgba(39,180,157,.10)',borderDash:[6,4],fill:true,tension:.3,pointRadius:1,borderWidth:2}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{usePointStyle:true,boxWidth:8,color:'#7f8aa1',font:{size:11}}}},scales:{x:{grid:{display:false},ticks:{maxTicksLimit:9,color:'#9aa3b6'}},y:{beginAtZero:true,grid:{color:'#f0f2f7'},ticks:{color:'#9aa3b6'}}}}});
}
document.addEventListener('DOMContentLoaded',()=>{
 const search=document.getElementById('tableSearch');
 if(search){search.addEventListener('input',()=>{const q=search.value.toLowerCase();document.querySelectorAll('#searchTable tbody tr').forEach(row=>row.style.display=row.innerText.toLowerCase().includes(q)?'':'none')})}
});
