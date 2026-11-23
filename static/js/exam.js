(function(){
 var cfg=window.EXAM,Q=cfg.questions,idx=0,ans={},review={},seen={},end=Date.now()+cfg.left*1000,submitting=false;
 var KEY='exam-'+cfg.rid;
 try{var st=JSON.parse(localStorage.getItem(KEY)||'{}');review=st.review||{};}catch(e){}
 Object.keys(cfg.saved).forEach(function(k){ans[k]=cfg.saved[k]});
 var $=function(id){return document.getElementById(id)};
 function persist(){try{localStorage.setItem(KEY,JSON.stringify({review:review}))}catch(e){}}
 function draw(){
  var q=Q[idx];seen[q.id]=1;
  $('qno').textContent='Question '+(idx+1)+' of '+Q.length;$('qtext').textContent=q.text;
  var h='';q.options.forEach(function(o){h+='<label class="opt"><input type="radio" name="o" value="'+o.id+'"'+(ans[q.id]==o.id?' checked':'')+'> <b>'+o.label+'.</b> <span class="o"></span></label>'});
  $('opts').innerHTML=h;
  var spans=$('opts').querySelectorAll('.o');q.options.forEach(function(o,i){spans[i].textContent=o.text});
  $('review').checked=!!review[q.id];
  $('prev').disabled=idx===0;$('next').disabled=idx===Q.length-1;
  var p='';Q.forEach(function(x,i){var c='pbtn';if(review[x.id])c+=' review';else if(ans[x.id])c+=' answered';else if(seen[x.id])c+=' seen';if(i===idx)c+=' current';
   p+='<button type="button" class="'+c+'" data-i="'+i+'" aria-label="Go to question '+(i+1)+'">'+(i+1)+'</button>'});
  $('palette').innerHTML=p;
  var a=0,r=0;Q.forEach(function(x){if(ans[x.id])a++;if(review[x.id])r++});
  $('cnt').textContent=a+' answered, '+r+' marked for review, '+(Q.length-a)+' not answered';
 }
 function save(qid,oid){fetch(cfg.saveUrl,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q:qid,o:oid})}).catch(function(){})}
 $('opts').addEventListener('change',function(e){if(e.target.name==='o'){var q=Q[idx];ans[q.id]=+e.target.value;save(q.id,+e.target.value);draw()}});
 $('clear').onclick=function(){var q=Q[idx];delete ans[q.id];save(q.id,null);draw()};
 $('review').onchange=function(e){var q=Q[idx];if(e.target.checked)review[q.id]=1;else delete review[q.id];persist();draw()};
 $('prev').onclick=function(){if(idx>0){idx--;draw()}};$('next').onclick=function(){if(idx<Q.length-1){idx++;draw()}};
 $('palette').onclick=function(e){var b=e.target.closest('[data-i]');if(b){idx=+b.dataset.i;draw()}};
 function submit(auto){
  if(submitting)return;
  if(!auto){var left=Q.filter(function(x){return !ans[x.id]}).length;
   if(!confirm('Submit the test now?'+(left?' '+left+' question(s) are unanswered.':'')))return;}
  submitting=true;
  fetch(cfg.submitUrl,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({answers:ans})})
   .then(function(r){return r.json()}).then(function(d){try{localStorage.removeItem(KEY)}catch(e){}location.href=d.redirect})
   .catch(function(){submitting=false;alert('Could not submit - check your connection and press Submit again.')});
 }
 $('submit').onclick=function(){submit(false)};
 function tick(){var s=Math.max(0,Math.round((end-Date.now())/1000)),m=Math.floor(s/60),x=s%60;
  $('timer').textContent=(m<10?'0':'')+m+':'+(x<10?'0':'')+x;$('timer').classList.toggle('low',s<=300);
  if(s<=0){clearInterval(iv);submit(true)}}
 var iv=setInterval(tick,1000);tick();draw();
 window.addEventListener('beforeunload',function(e){if(!submitting){e.preventDefault();e.returnValue=''}});
})();
