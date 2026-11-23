(function(){
 var root=document.documentElement,saved=localStorage.getItem('theme');
 if(saved)root.setAttribute('data-bs-theme',saved);
 document.addEventListener('click',function(e){
  var t=e.target.closest('[data-theme-toggle]');
  if(t){var n=root.getAttribute('data-bs-theme')==='dark'?'light':'dark';root.setAttribute('data-bs-theme',n);localStorage.setItem('theme',n);}
  var m=e.target.closest('[data-menu]');if(m)document.querySelector('.sidebar').classList.toggle('open');
  var b=e.target.closest('[data-bookmark]');
  if(b){fetch(b.dataset.bookmark,{method:'POST'}).then(function(r){if(r.status===401||r.redirected){location.href='/login';return null}return r.json()})
   .then(function(d){if(d)b.textContent=d.saved?'Saved':'Save'}).catch(function(){b.textContent='Retry'});}
  var o=e.target.closest('[data-reveal] .opt');
  if(o){var box=o.closest('[data-reveal]');if(box.dataset.done)return;box.dataset.done=1;
   box.querySelectorAll('.opt').forEach(function(x){var ok=x.dataset.correct==='1';
     if(ok)x.classList.add('right');else if(x===o)x.classList.add('wrong');
     x.nextElementSibling.hidden=false;});
   var r=box.querySelector('.result');r.textContent=o.dataset.correct==='1'?'Correct':'Incorrect - see the explanations below';r.hidden=false;}
 });
})();
