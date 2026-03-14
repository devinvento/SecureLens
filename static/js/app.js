// Generic API wrapper
function getToken() {
    // Check for new key first, then fall back to old key for backward compatibility
    return localStorage.getItem("access_token") || localStorage.getItem("token");
}

function getRefreshToken() {
    return localStorage.getItem("refresh_token");
}

function setTokens(accessToken, refreshToken) {
    // Clear old token key and set new keys
    localStorage.removeItem("token");
    localStorage.setItem("access_token", accessToken);
    if (refreshToken) {
        localStorage.setItem("refresh_token", refreshToken);
    }
}

function checkAuth() {
    if (!getToken()) {
        window.location.href = "/";
        return false;
    }
    return true;
}

function logoutUser() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    window.location.href = "/";
}

// Try to refresh the access token using the refresh token
async function tryRefreshToken() {
    const refreshToken = getRefreshToken();
    if (!refreshToken) {
        return false;
    }
    
    try {
        const response = await fetch("/api/auth/refresh", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ refresh_token: refreshToken })
        });
        
        if (response.ok) {
            const data = await response.json();
            localStorage.setItem("access_token", data.access_token);
            return true;
        }
    } catch (err) {
        console.error("Token refresh failed:", err);
    }
    
    return false;
}

// Handle 401 errors with token refresh
async function handleUnauthorized(originalFetch, ...args) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
        return await originalFetch(...args);
    }
    logoutUser();
    return null;
}

async function loginUser(username, password) {
    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);

    try {
        const response = await LoaderManager.fetchWithLoader("/api/auth/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: formData.toString()
        }, "Logging in...");
        
        const data = await response.json();
        if(response.ok) {
            if (data.status === "2FA_REQUIRED") {
                return { status: "2FA_REQUIRED", email: data.email };
            }
            setTokens(data.access_token, data.refresh_token);
            return { token: data.access_token };
        } else {
            return { error: data.detail || "Login failed" };
        }
    } catch (err) {
        return { error: "Network error" };
    }
}

async function verify2FA(email, token) {
    try {
        const response = await LoaderManager.fetchWithLoader("/api/auth/verify-2fa?" + new URLSearchParams({ email, token }), {
            method: "POST"
        }, "Verifying 2FA...");
        
        const data = await response.json();
        if(response.ok) {
            setTokens(data.access_token, data.refresh_token);
            return { token: data.access_token };
        } else {
            return { error: data.detail || "Invalid 2FA code" };
        }
    } catch (err) {
        return { error: "Network error" };
    }
}

async function fetchAPI(endpoint, loadingText = null) {
    const token = getToken();
    const res = await LoaderManager.fetchWithLoader(endpoint, {
        headers: { "Authorization": `Bearer ${token}` }
    }, loadingText);
    if(res.status === 401) {
        // Try to refresh token before logging out
        const refreshed = await tryRefreshToken();
        if (refreshed) {
            // Retry the request with new token
            const newToken = getToken();
            const retryRes = await LoaderManager.fetchWithLoader(endpoint, {
                headers: { "Authorization": `Bearer ${newToken}` }
            }, loadingText);
            if (retryRes.status === 401) {
                logoutUser();
                return null;
            }
            return await retryRes.json();
        }
        logoutUser();
        return null;
    }
    return await res.json();
}

async function postAPI(endpoint, payload, loadingText = null) {
    const token = getToken();
    const res = await LoaderManager.fetchWithLoader(endpoint, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify(payload)
    }, loadingText);
    if(res.status === 401) {
        // Try to refresh token before logging out
        const refreshed = await tryRefreshToken();
        if (refreshed) {
            // Retry the request with new token
            const newToken = getToken();
            const retryRes = await LoaderManager.fetchWithLoader(endpoint, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${newToken}`
                },
                body: JSON.stringify(payload)
            }, loadingText);
            if (retryRes.status === 401) {
                logoutUser();
                return null;
            }
            return await retryRes.json();
        }
        logoutUser();
        return null;
    }
    return await res.json();
}

async function deleteAPI(endpoint, loadingText = null) {
    const token = getToken();
    const res = await LoaderManager.fetchWithLoader(endpoint, {
        method: "DELETE",
        headers: {
            "Authorization": `Bearer ${token}`
        }
    }, loadingText);
    if(res.status === 401) {
        // Try to refresh token before logging out
        const refreshed = await tryRefreshToken();
        if (refreshed) {
            // Retry the request with new token
            const newToken = getToken();
            const retryRes = await LoaderManager.fetchWithLoader(endpoint, {
                method: "DELETE",
                headers: {
                    "Authorization": `Bearer ${newToken}`
                }
            }, loadingText);
            if (retryRes.status === 401) {
                logoutUser();
                return null;
            }
            return await retryRes.json();
        }
        logoutUser();
        return null;
    }
    return await res.json();
}

function formatExecutionTime(seconds) {
    if (seconds === null || seconds === undefined || seconds === 0) {
        return "0s";
    }
    
    const totalSeconds = Math.floor(seconds);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;
    
    let parts = [];
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0) parts.push(`${minutes}m`);
    if (secs > 0 || parts.length === 0) parts.push(`${secs}s`);
    
    return parts.join(" ");
}

