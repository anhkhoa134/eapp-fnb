(() => {
    if (window.eappBillingPeriodsInitialized) return;
    window.eappBillingPeriodsInitialized = true;
    document.addEventListener('click', (event) => {
        const button = event.target.closest('[data-billing-period-button]');
        if (!button) return;
        const pricing = button.closest('[data-billing-period]');
        if (!pricing) return;
        pricing.dataset.billingPeriod = button.dataset.billingPeriodButton;
        pricing.querySelectorAll('[data-billing-period-button]').forEach((item) => {
            item.setAttribute('aria-pressed', String(item === button));
        });
    });
})();
