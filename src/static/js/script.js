document.addEventListener('DOMContentLoaded', function() {
    const transcriptForm = document.getElementById('transcriptForm');
    const videoUrlInput = document.getElementById('videoUrl');
    const playlistUrlInput = document.getElementById('playlistUrl');
    const maxVideosInput = document.getElementById('maxVideos');
    const languageSelect = document.getElementById('language');
    const extractBtn = document.getElementById('extractBtn');
    const loadingSection = document.getElementById('loadingSection');
    const resultSection = document.getElementById('resultSection');
    const contentTitle = document.getElementById('contentTitle');
    const transcriptResult = document.getElementById('transcriptResult');
    const copyBtn = document.getElementById('copyBtn');
    const downloadBtn = document.getElementById('downloadBtn');
    const summarySection = document.getElementById('summarySection');
    const totalVideos = document.getElementById('totalVideos');
    const successVideos = document.getElementById('successVideos');
    const fallbackVideos = document.getElementById('fallbackVideos');
    const failedVideos = document.getElementById('failedVideos');

    // Theme toggle logic
    const themeToggle = document.getElementById('themeToggle');
    const htmlEl = document.documentElement;
    // Set theme from localStorage or default
    function setTheme(theme) {
        htmlEl.setAttribute('data-theme', theme);
        if (theme === 'dark') {
            themeToggle.checked = true;
        } else {
            themeToggle.checked = false;
        }
    }
    // On load
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark' || savedTheme === 'light') {
        setTheme(savedTheme);
    } else {
        setTheme('light');
    }
    // On toggle
    themeToggle.addEventListener('change', function() {
        const newTheme = themeToggle.checked ? 'dark' : 'light';
        setTheme(newTheme);
        localStorage.setItem('theme', newTheme);
    });

    // When form is submitted
    transcriptForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Check active tab
        const activeTab = document.querySelector('.nav-link.active');
        const isPlaylist = activeTab.id === 'playlist-tab';
        
        const url = isPlaylist ? playlistUrlInput.value.trim() : videoUrlInput.value.trim();
        const language = languageSelect.value;
        const maxVideos = isPlaylist ? parseInt(maxVideosInput.value) : 1;
        
        if (!url) {
            alert('Please enter a valid YouTube URL');
            return;
        }
        
        // Update UI state
        extractBtn.disabled = true;
        loadingSection.classList.remove('d-none');
        resultSection.classList.add('d-none');
        summarySection.classList.add('d-none');
        
        // Send API request
        fetch('/extract', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: url,
                language: language,
                max_videos: maxVideos
            }),
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Server error');
            }
            return response.json();
        })
        .then(data => {
            // Show results
            contentTitle.textContent = data.title || 'Transcript';
            transcriptResult.textContent = data.transcript;
            
            // Show summary information
            if (data.summary) {
                totalVideos.textContent = data.summary.total;
                successVideos.textContent = data.summary.success;
                fallbackVideos.textContent = data.summary.fallback;
                failedVideos.textContent = data.summary.failed;
                
                // Language information
                const languageInfo = document.getElementById('languageInfo');
                if (data.summary.languages && data.summary.languages.length > 0) {
                    const languageMap = {
                        'en': 'English',
                        'tr': 'Turkish',
                        'de': 'German',
                        'fr': 'French',
                        'es': 'Spanish'
                    };
                    
                    const languageNames = data.summary.languages.map(lang => 
                        languageMap[lang] || lang
                    );
                    
                    languageInfo.textContent = 'Languages used: ' + languageNames.join(', ');
                } else {
                    languageInfo.textContent = '';
                }
                
                summarySection.classList.remove('d-none');
            }
            
            // Update UI state
            loadingSection.classList.add('d-none');
            resultSection.classList.remove('d-none');
            extractBtn.disabled = false;
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while extracting transcript: ' + error.message);
            loadingSection.classList.add('d-none');
            extractBtn.disabled = false;
        });
    });

    // Copy button
    copyBtn.addEventListener('click', function() {
        const text = transcriptResult.textContent;
        navigator.clipboard.writeText(text)
            .then(() => {
                const originalText = copyBtn.textContent;
                copyBtn.textContent = 'Copied!';
                setTimeout(() => {
                    copyBtn.textContent = originalText;
                }, 2000);
            })
            .catch(err => {
                console.error('Copy error:', err);
                alert('Copy operation failed');
            });
    });

    // Download button
    downloadBtn.addEventListener('click', function() {
        const text = transcriptResult.textContent;
        const title = contentTitle.textContent.replace(/[^a-z0-9]/gi, '_').toLowerCase();
        const filename = `${title}_transcript.txt`;
        
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        
        // Cleanup
        setTimeout(() => {
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }, 100);
    });
});
