import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './index.css';

const GA_ID = 'G-8Z0X9ZJFH9';

function trackPageView() {
  window.gtag?.('config', GA_ID, {
    page_path: `${window.location.pathname}${window.location.search}${window.location.hash || '#sing'}`,
  });
}

trackPageView();
window.addEventListener('hashchange', trackPageView);

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>
);
