const {defineConfig} = require('@playwright/test');
module.exports = defineConfig({testDir:'./tests',timeout:120000,workers:1,use:{baseURL:process.env.WEB_URL||'http://localhost:3000',trace:'retain-on-failure',screenshot:'only-on-failure'},reporter:[['list'],['junit',{outputFile:'test-results/browser.xml'}]]});
