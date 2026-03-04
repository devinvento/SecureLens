// Generic API wrapper
function getToken() {
    return localStorage.getItem("token");
}

function checkAuth() {
    if (!getToken()) {
        window.location.href = "/";
        return false;
    }
    return true;
}

function logoutUser() {
    localStorage.removeItem("token");
    window.location.href = "/";
}

async function loginUser(username, password) {
    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);

    try {
        const response = await fetch("/api/auth/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: formData.toString()
        });
        
        const data = await response.json();
        if(response.ok) {
            localStorage.setItem("token", data.access_token);
            return { token: data.access_token };
        } else {
            return { error: data.detail || "Login failed" };
        }
    } catch (err) {
        return { error: "Network error" };
    }
}

async function fetchAPI(endpoint) {
    const token = getToken();
    const res = await fetch(endpoint, {
        headers: { "Authorization": `Bearer ${token}` }
    });
    if(res.status === 401) {
        logoutUser();
        return null;
    }
    return await res.json();
}

async function postAPI(endpoint, payload) {
    const token = getToken();
    const res = await fetch(endpoint, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify(payload)
    });
    if(res.status === 401) {
        logoutUser();
        return null;
    }
    return await res.json();
}
