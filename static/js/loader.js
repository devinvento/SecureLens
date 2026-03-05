/**
 * Loader Manager - Global Loading Utilities
 * Handles button loading states and full-screen loaders using SweetAlert2.
 */

class LoaderManager {
    static getLoaderConfig(loadingText) {
        return {
            title: loadingText,
            allowOutsideClick: false,
            width: 600,
            padding: '2em',
            color: '#fff',
            background: 'transparent',
            backdrop: `rgba(0,0,0,0.4)`,
            customClass: {
                container: 'loader-manager-container',
                popup: 'loader-manager-popup',
                title: 'loader-manager-title',
                loader: 'loader-manager-loader'
            },
            didOpen: () => {
                Swal.showLoading();
            }
        };
    }

    static async withLoader(action, loadingText = 'Processing...') {
        Swal.fire(LoaderManager.getLoaderConfig(loadingText));

        try {
            await action();
        } catch (error) {
            console.error(error);
            throw error;
        } finally {
            Swal.close();
        }
    }

    static setButtonLoading(buttonOrId, isLoading, loadingText = 'Loading...') {
        let button = buttonOrId;
        if (typeof buttonOrId === 'string') {
            button = document.getElementById(buttonOrId);
        }
        if (!button) return;

        if (isLoading) {
            // Store original content if not already stored
            if (!button.dataset.originalContent) {
                button.dataset.originalContent = button.innerHTML;
            }
            // Disable and show spinner
            button.disabled = true;
            button.innerHTML = `
                <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                ${loadingText}
            `;
        } else {
            // Restore original content
            button.disabled = false;
            if (button.dataset.originalContent) {
                button.innerHTML = button.dataset.originalContent;
            }
        }
    }

    // Helper for Fetch API interactions with optional loader
    static async fetchWithLoader(url, options = {}, loadingText = null) {
        // Show loader if loadingText is provided
        if (loadingText) {
            Swal.fire(LoaderManager.getLoaderConfig(loadingText));
        }
        
        try {
            const response = await fetch(url, options);
            if (loadingText) {
                Swal.close();
            }
            return response;
        } catch (error) {
            if (loadingText) {
                Swal.close();
            }
            throw error;
        }
    }

    static injectStyles() {
        const styleId = 'loader-manager-styles';
        if (document.getElementById(styleId)) return;

        const styles = `
            .loader-manager-container {
                backdrop-filter: blur(12px) !important;
                -webkit-backdrop-filter: blur(12px) !important;
                background: linear-gradient(135deg, rgba(30, 60, 114, 0.6) 0%, rgba(42, 82, 152, 0.6) 100%) !important;
            }
            
            .loader-manager-popup {
                background: rgba(255, 255, 255, 0.1) !important;
                backdrop-filter: blur(10px) !important;
                -webkit-backdrop-filter: blur(10px) !important;
                border-radius: 20px !important;
                box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37) !important;
                border: 1px solid rgba(255, 255, 255, 0.18) !important;
            }
            
            .loader-manager-title {
                color: #ffffff !important;
                font-weight: 600 !important;
                font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
                font-size: 1.2rem !important;
                margin-top: 1.5rem !important;
                letter-spacing: 0.5px !important;
                text-shadow: 0 2px 4px rgba(0,0,0,0.2) !important;
            }

            .loader-manager-loader {
                border-color: #fff transparent #fff transparent !important;
            }
        `;

        const styleSheet = document.createElement("style");
        styleSheet.id = styleId;
        styleSheet.innerText = styles;
        document.head.appendChild(styleSheet);
    }
}

// Initialize styles
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', LoaderManager.injectStyles);
} else {
    LoaderManager.injectStyles();
}

// Make it available globally
window.LoaderManager = LoaderManager;
window.fetchWithLoader = LoaderManager.fetchWithLoader;
