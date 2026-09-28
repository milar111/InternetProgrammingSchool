function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + '=') {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

export async function ensureCsrfToken() {
  await fetch('/api/auth/csrf/', {
    method: 'GET',
    credentials: 'include',
  });
  return getCookie('csrftoken');
}

async function apiRequest(url, options = {}) {
  const method = options.method || 'GET';
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method.toUpperCase())) {
    let csrfToken = getCookie('csrftoken');
    if (!csrfToken) {
      csrfToken = await ensureCsrfToken();
    }
    if (csrfToken) {
      headers['X-CSRFToken'] = csrfToken;
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (response.status === 204) {
    return null;
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const error = new Error('API Request Failed');
    error.status = response.status;
    error.errors = data.errors || { non_field_errors: ['An unexpected error occurred.'] };
    throw error;
  }

  return data;
}

export const authApi = {
  getCsrf: ensureCsrfToken,

  register: (payload) =>
    apiRequest('/api/auth/register/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  login: (payload) =>
    apiRequest('/api/auth/login/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  logout: () =>
    apiRequest('/api/auth/logout/', {
      method: 'POST',
    }),

  getMe: () =>
    apiRequest('/api/auth/me/', {
      method: 'GET',
    }),

  updateProfile: (payload) =>
    apiRequest('/api/auth/me/', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
};
