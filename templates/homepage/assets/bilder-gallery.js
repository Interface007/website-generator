document.addEventListener('DOMContentLoaded', function () {
  const accordionItems = Array.from(document.querySelectorAll('[data-accordion-item]'));

  function scrollAccordionItemIntoView(item) {
    if (!item) {
      return;
    }
    requestAnimationFrame(function () {
      item.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  accordionItems.forEach(function (item) {
    const button = item.querySelector('.galerie-accordion-toggle');
    const panel = item.querySelector('.galerie-accordion-panel');
    if (!button || !panel) {
      return;
    }

    button.addEventListener('click', function () {
      const isExpanded = button.getAttribute('aria-expanded') === 'true';
      accordionItems.forEach(function (otherItem) {
        const otherButton = otherItem.querySelector('.galerie-accordion-toggle');
        const otherPanel = otherItem.querySelector('.galerie-accordion-panel');
        if (!otherButton || !otherPanel) {
          return;
        }
        otherButton.setAttribute('aria-expanded', 'false');
        otherPanel.hidden = true;
      });

      if (!isExpanded) {
        button.setAttribute('aria-expanded', 'true');
        panel.hidden = false;
        scrollAccordionItemIntoView(item);
      }
    });
  });

  var hashDate = '';
  if (window.location.hash) {
    var hashMatch = window.location.hash.match(/^#galerie-(\d{4}-\d{2}-\d{2})$/);
    if (hashMatch) { hashDate = hashMatch[1]; }
  }
  var targetItem = null;
  if (hashDate) {
    targetItem = accordionItems.find(function (it) {
      return it.getAttribute('data-gallery-date') === hashDate;
    }) || null;
  }
  if (!targetItem && accordionItems.length > 0) {
    targetItem = accordionItems[0];
  }
  if (targetItem) {
    var targetButton = targetItem.querySelector('.galerie-accordion-toggle');
    var targetPanel = targetItem.querySelector('.galerie-accordion-panel');
    if (targetButton && targetPanel) {
      targetButton.setAttribute('aria-expanded', 'true');
      targetPanel.hidden = false;
      if (hashDate) {
        scrollAccordionItemIntoView(targetItem);
      }
    }
  }

  if (typeof GLightbox !== 'undefined') {
    const lightbox = GLightbox({ selector: '.glightbox', loop: true, touchNavigation: true });
    lightbox.on('slide_after_load', function (event) {
      const slideVideo = event.slideNode ? event.slideNode.querySelector('video') : null;
      if (!slideVideo) {
        return;
      }

      const trigger = event.triggerNode || event.trigger || null;
      let rotation = trigger ? trigger.getAttribute('data-rotate') : null;
      if (rotation !== 'left' && rotation !== 'right') {
        const sourceEl = slideVideo.querySelector('source');
        const videoSrc = slideVideo.currentSrc || slideVideo.getAttribute('src') || (sourceEl ? sourceEl.getAttribute('src') : '') || '';
        if (/-rotate-left\.[^./?]+($|\?)/i.test(videoSrc)) {
          rotation = 'left';
        } else if (/-rotate-right\.[^./?]+($|\?)/i.test(videoSrc)) {
          rotation = 'right';
        }
      }
      if (rotation !== 'left' && rotation !== 'right') {
        return;
      }

      slideVideo.style.transform = rotation === 'left' ? 'rotate(-90deg)' : 'rotate(90deg)';
      slideVideo.style.transformOrigin = 'center center';
      slideVideo.style.maxWidth = 'min(90vh, 900px)';
      slideVideo.style.maxHeight = 'min(90vw, 1200px)';
    });
  }
});
