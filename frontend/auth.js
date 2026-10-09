(() => {
  const config=window.SIGNBRIDGE_CONFIG;
  const gate=document.getElementById("authGate");
  const message=document.getElementById("authMessage");
  const logout=document.getElementById("logoutBtn");
  if (!window.supabase || !config?.supabaseUrl || config.supabaseUrl.includes("YOUR_PROJECT") || !config?.supabaseAnonKey) {
    message.textContent="Sign-in is not configured yet. Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY on the hosting service."; return;
  }
  const client=window.supabase.createClient(config.supabaseUrl,config.supabaseAnonKey,{
    auth:{flowType:"pkce",autoRefreshToken:true,persistSession:true,detectSessionInUrl:true}
  });
  window.signbridgeAuth=client.auth;
  let currentUser=null;
  let recovering=false;
  async function setSession(session) {
    const id=session?.user?.id || null;
    gate.hidden=!!id;
    gate.style.display=id?"none":"grid";
    logout.hidden=!id;
    if (currentUser!==id) {
      currentUser=id;
      if (!id) { window.speechSynthesis?.cancel(); location.reload(); }
      else window.dispatchEvent(new Event("signbridge-signed-in"));
    }
  }
  client.auth.onAuthStateChange((event,session)=>{
    if(event==="PASSWORD_RECOVERY") {
      recovering=true; gate.hidden=false;gate.style.display="grid";
      message.textContent="Enter your new password below.";
      document.getElementById("authEmail").required=false;
      document.getElementById("authEmail").parentElement.hidden=true;
      document.querySelector("#authForm button").textContent="Save new password";
      document.getElementById("authPassword").autocomplete="new-password";
      for(const id of ["signUpBtn","googleLoginBtn","resetPasswordBtn"])document.getElementById(id).hidden=true;
    } else if(!recovering) setSession(session);
  });
  client.auth.getSession().then(({data})=>{if(!recovering)setSession(data.session);});
  const email=()=>document.getElementById("authEmail").value.trim();
  const password=()=>document.getElementById("authPassword").value;
  async function run(fn) { message.textContent="Working..."; try {const {error,data}=await fn();if(error)throw error;message.textContent=data?.session?"Signed in.":"Check your email for the confirmation link."; } catch(e){message.textContent=e.message||"Authentication failed";} }
  document.getElementById("authForm").onsubmit=async e=>{
    e.preventDefault();
    if(!recovering) return run(()=>client.auth.signInWithPassword({email:email(),password:password()}));
    message.textContent="Updating password...";
    try { const {error}=await client.auth.updateUser({password:password()});if(error)throw error;location.reload(); }
    catch(error){message.textContent=error.message;}
  };
  document.getElementById("signUpBtn").onclick=()=>run(()=>client.auth.signUp({email:email(),password:password(),options:{emailRedirectTo:location.origin}}));
  document.getElementById("googleLoginBtn").onclick=()=>run(()=>client.auth.signInWithOAuth({provider:"google",options:{redirectTo:location.origin}}));
  document.getElementById("resetPasswordBtn").onclick=()=>run(()=>client.auth.resetPasswordForEmail(email(),{redirectTo:location.origin}));
  logout.onclick=async()=>{await client.auth.signOut();location.reload();};
})();
