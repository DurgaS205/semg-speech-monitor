


// LOGIN LOGIC

document.getElementById("loginForm").addEventListener("submit", function(e){

e.preventDefault();

const email = document.getElementById("email").value;
const password = document.getElementById("password").value;

const correctEmail = "sarahthomas8765@gmail.com";
const correctPassword = "12345";

if(email === correctEmail && password === correctPassword){

window.location.href = "dashboard.html";

}
else{

document.getElementById("error").innerText = "Invalid email or password";

}

});


// SLIDESHOW LOGIC

const images = [
"../assets/slide1.jpg",
"../assets/slide 2.jpg",
"../assets/slide 3.jpg",
"../assets/slide 4.jpg",
"../assets/slide 5.jpg"
];

let index = 0;

function changeBackground(){

const container = document.querySelector(".slideshow-container");

container.style.backgroundImage = "url(' "+images[index] + " ')";

index++;

if(index >= images.length){
index = 0;
}

}
setInterval(changeBackground, 5000);

changeBackground();

