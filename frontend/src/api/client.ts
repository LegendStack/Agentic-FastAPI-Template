import axios from 'axios';

const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL || '/api/v1',
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor to add Bearer tokens later
api.interceptors.request.use((config) => {
    // We will bridge MSAL tokens here via a custom hook or global state
    return config;
}, (error) => {
    return Promise.reject(error);
});

export default api;
