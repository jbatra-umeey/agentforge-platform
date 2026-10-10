const {test,expect}=require('@playwright/test');
const keys=JSON.parse(process.env.AGENTFORGE_KEYS||'{}');
const keyFor=role=>Object.keys(keys).find(k=>keys[k].role===role);
async function login(page,role){await page.getByLabel('Scoped API key').fill(keyFor(role));await page.getByRole('button',{name:'Connect',exact:true}).click();await expect(page.getByRole('button',{name:'Switch identity'})).toBeVisible()}

test('evidence → cited knowledge run → artifact',async({page})=>{
 await page.goto('/');await login(page,'operator');
 await page.getByRole('button',{name:'Evidence library'}).click();
 await page.getByRole('button',{name:'Save evidence'}).click();
 await expect(page.getByRole('alert')).toContainText('Evidence saved');
 await page.getByRole('button',{name:'Workbench',exact:false}).click();
 await page.getByRole('button',{name:/Knowledge investigator Search/}).click();
 await page.getByRole('button',{name:/Start workflow/}).click();
 await expect(page.getByRole('button',{name:'Download execution artifact',exact:false})).toBeVisible({timeout:90000});
 await expect(page.locator('.execution')).toContainText('citation_quotes_valid');
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Download execution artifact',exact:false}).click();
 expect((await download).suggestedFilename()).toMatch(/agentforge-.*\.json/);
});

test('operator proposes → independent approver resumes → real repair tests',async({page})=>{
 await page.goto('/');await login(page,'operator');
 await page.getByRole('button',{name:/SDLC engineer Reproduce/}).click();
 await page.getByRole('button',{name:/Start workflow/}).click();
 await expect(page.getByText('Independent review required')).toBeVisible({timeout:90000});
 await expect(page.getByRole('button',{name:'Approve execution'})).toBeDisabled();
 await page.getByRole('button',{name:'Switch identity'}).click();await login(page,'approver');
 await page.locator('.run-row').filter({hasText:'sdlc'}).first().click();
 await page.getByRole('button',{name:'Approve execution'}).click();
 await expect(page.getByRole('button',{name:'Download execution artifact',exact:false})).toBeVisible({timeout:90000});
 await expect(page.locator('.execution')).toContainText('4 subscription assertions passed');
});

test('mobile layout and accessible sign-in',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto('/');
 await expect(page.getByRole('heading',{name:'From intent to verified execution.'})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
 await page.getByLabel('Scoped API key').fill('invalid');await page.getByRole('button',{name:'Connect',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('Valid bearer credential required');
});
