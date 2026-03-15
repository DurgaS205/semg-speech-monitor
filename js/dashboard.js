function openGraph(){

window.location.href = "semg_graph.html";
function goToLogin(){
window.location.href = "login.html";
}
}
const toggle = document.getElementById("monitorToggle");
const deviceStatus = document.getElementById("deviceStatus");
const electrodeStatus = document.getElementById("electrodeStatus");

toggle.addEventListener("change", function(){

if(toggle.checked){

deviceStatus.textContent = "Connected";
electrodeStatus.textContent = "Active";

}
else{

deviceStatus.textContent = "Disconnected";
electrodeStatus.textContent = "Inactive";

}

});