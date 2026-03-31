document.addEventListener('DOMContentLoaded', () => {
  /* -------------------------------------------
     1. SCROLL NAVBAR
  ------------------------------------------- */
  const navbar = document.getElementById('navbar');
  window.addEventListener('scroll', () => {
    if (window.scrollY > 50) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }
  });

  /* -------------------------------------------
     2. MAGNETIC BUTTONS & LINKS
  ------------------------------------------- */
  const magnetics = document.querySelectorAll('.magnetic, .magnetic-text');

  magnetics.forEach(elem => {
    elem.addEventListener('mousemove', function(e) {
      const rect = this.getBoundingClientRect();
      const h = rect.height;
      const w = rect.width;
      const x = e.clientX - rect.left - w / 2;
      const y = e.clientY - rect.top - h / 2;

      // Calculate translation based on class type
      const isText = this.classList.contains('magnetic-text');
      const sensitivity = isText ? 0.2 : 0.4;
      
      const xMove = x * sensitivity;
      const yMove = y * sensitivity;

      this.style.transform = `translate(${xMove}px, ${yMove}px)`;
    });

    elem.addEventListener('mouseleave', function() {
      // Reset position smoothly
      this.style.transition = 'transform 0.5s cubic-bezier(0.25, 1, 0.5, 1)';
      this.style.transform = 'translate(0px, 0px)';
      
      // Remove transition after it's done so mousemove is snappy again
      setTimeout(() => {
        this.style.transition = '';
      }, 500);
    });
  });

  /* -------------------------------------------
     3. TILT EFFECT FOR CARDS
  ------------------------------------------- */
  const cards = document.querySelectorAll('.tilt-card');
  
  cards.forEach(card => {
    const inner = card.querySelector('.card-inner');
    if (!inner) return; // safety
    
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      
      const rotateX = ((y - centerY) / centerY) * -22; 
      const rotateY = ((x - centerX) / centerX) * 22;

      inner.style.transform = `rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(1.05)`;
      
      const px = (x / rect.width) * 100;
      const py = (y / rect.height) * 100;
      inner.style.setProperty('--px', `${px}%`);
      inner.style.setProperty('--py', `${py}%`);
    });

    card.addEventListener('mouseleave', () => {
      inner.style.transform = 'rotateX(0) rotateY(0) scale(1)';
      inner.style.transition = 'transform 0.5s cubic-bezier(0.25, 1, 0.5, 1)';
      inner.style.setProperty('--px', `50%`);
      inner.style.setProperty('--py', `50%`);
      setTimeout(() => { inner.style.transition = ''; }, 500);
    });
  });

  /* -------------------------------------------
     4. REVEAL ANIMATIONS
  ------------------------------------------- */
  const revealElements = document.querySelectorAll('.reveal');
  const revealOptions = {
    threshold: 0.15,
    rootMargin: "0px 0px -50px 0px"
  };

  if ('IntersectionObserver' in window) {
    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('active');
          observer.unobserve(entry.target);
        }
      });
    }, revealOptions);

    revealElements.forEach(el => revealObserver.observe(el));
  } else {
    // Fallback for older browsers
    revealElements.forEach(el => el.classList.add('active'));
  }
  
  // Failsafe: Trigger all reveals after 1.5 seconds so they are never permanently hidden
  setTimeout(() => {
    revealElements.forEach(el => el.classList.add('active'));
  }, 1500);

  /* -------------------------------------------
     5. NATIVE DRAG SCROLL FOR CAROUSEL
  ------------------------------------------- */
  const track = document.querySelector('.smooothy-track');
  let isDown = false;
  let startX;
  let scrollLeft;

  if (track) {
    track.addEventListener('mousedown', (e) => {
      isDown = true;
      track.classList.add('active'); // apply active styles
      startX = e.pageX - track.offsetLeft;
      scrollLeft = track.scrollLeft;
      // Disable smooth snap while dragging
      track.style.scrollSnapType = 'none';
    });
    track.addEventListener('mouseleave', () => {
      isDown = false;
      track.classList.remove('active');
      track.style.scrollSnapType = 'x mandatory';
    });
    track.addEventListener('mouseup', () => {
      isDown = false;
      track.classList.remove('active');
      track.style.scrollSnapType = 'x mandatory';
    });
    track.addEventListener('mousemove', (e) => {
      if (!isDown) return;
      e.preventDefault();
      const x = e.pageX - track.offsetLeft;
      const walk = (x - startX) * 2; // scroll-fast multiplier
      track.scrollLeft = scrollLeft - walk;
    });
  }

  /* -------------------------------------------
     6. ARCHITECTURE NODE PULSE
  ------------------------------------------- */
  const nodes = document.querySelectorAll('.pulse-node');
  let currentNode = 0;
  
  setInterval(() => {
    nodes.forEach(n => n.classList.remove('focus-node'));
    if (nodes[currentNode]) {
      nodes[currentNode].classList.add('focus-node');
    }
    if (nodes.length > 0) {
      currentNode = (currentNode + 1) % nodes.length;
    }
  }, 3000);

  /* -------------------------------------------
     7. BACKGROUND COLOR TRANSITION ON SCROLL
  ------------------------------------------- */
  const sections = document.querySelectorAll('header[data-bg], section[data-bg]');
  const bgOptions = {
    rootMargin: "-40% 0px -40% 0px",
    threshold: 0
  };
  
  if ('IntersectionObserver' in window) {
    const bgObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const bg = entry.target.getAttribute('data-bg');
          if (bg) {
            document.body.style.backgroundColor = bg;
          }
        }
      });
    }, bgOptions);

    sections.forEach(sec => bgObserver.observe(sec));
  }
});