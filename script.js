// Simple JavaScript for the CS6604 Traffic Safety website

document.addEventListener('DOMContentLoaded', function() {
    // Add smooth scrolling for any anchor links
    const links = document.querySelectorAll('a[href^="#"]');
    
    links.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            const targetId = this.getAttribute('href');
            const targetElement = document.querySelector(targetId);
            
            if (targetElement) {
                targetElement.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });
    
    // Add a simple fade-in animation for the main content
    const content = document.querySelector('.content');
    if (content) {
        content.style.opacity = '0';
        content.style.transform = 'translateY(20px)';
        content.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        
        setTimeout(() => {
            content.style.opacity = '1';
            content.style.transform = 'translateY(0)';
        }, 100);
    }
    
    // Console message for developers
    console.log('CS6604 Traffic Safety website loaded successfully!');
});