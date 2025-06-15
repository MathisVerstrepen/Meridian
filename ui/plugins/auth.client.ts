export default defineNuxtPlugin(() => {
    const tokenCookie = useCookie('auth_token');

    if (tokenCookie.value) {
        console.log('Auth token found in cookie, moving to localStorage.');
        localStorage.setItem('access_token', tokenCookie.value);
        tokenCookie.value = null;
    }
});