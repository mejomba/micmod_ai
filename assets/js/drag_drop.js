

document.addEventListener('DOMContentLoaded', (event) => {

  var dragSrcEl = null;
  
  function handleDragStart(e) {
      console.log("handleDragStart")
    // this.style.opacity = '0.5';
    this.style.color = 'red';
    
    dragSrcEl = this;

    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', this.innerHTML);
  }

  function handleDragOver(e) {
    if (e.preventDefault) {
      e.preventDefault();
    }
      console.log("handleDragOver")
    e.dataTransfer.dropEffect = 'move';
    
    return false;
  }

  function handleDragEnter(e) {
      console.log("handleDragEnter")
    this.classList.add('over');
  }

  function handleDragLeave(e) {
      console.log("handleDragLeave")
    this.classList.remove('over');
      this.nextElementSibling.style.opacity = '1'

  }

  function handleDrop(e) {
      console.log("handleDrop")
    if (e.stopPropagation) {
      e.stopPropagation(); // stops the browser from redirecting.
    }
    
    if (dragSrcEl != this) {
      dragSrcEl.innerHTML = this.innerHTML;
      this.innerHTML = e.dataTransfer.getData('text/html');
    }
    this.style.color = 'red';
    dragSrcEl.style.color = 'black';
    let t = this
    setTimeout(function (){
      t.style.color = 'black';
    }, 600)
    return false;
  }

  function handleDragEnd(e) {
      console.log("handleDragEnd")
    // this.style.opacity = '1';
    this.nextElementSibling.style.opacity = '1'
      console.log(this.nextElementSibling)
    items.forEach(function (item) {
      item.classList.remove('over');
    });
  }
  
  
  let items = document.querySelectorAll('.item');
  items.forEach(function(item) {
    item.addEventListener('dragstart', handleDragStart, false);
    item.addEventListener('dragenter', handleDragEnter, false);
    item.addEventListener('dragover', handleDragOver, false);
    item.addEventListener('dragleave', handleDragLeave, false);
    item.addEventListener('drop', handleDrop, false);
    item.addEventListener('dragend', handleDragEnd, false);
  });
});