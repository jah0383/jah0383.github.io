
const MyInfo = {
	Name: "James Howe",
	FirstName: "James",
	LastName: "Howe",
	Age: 23,
	Phone: "(203) 524-4312",
	Email: "james.howe@kyndryl.com",
	AddressLine1: "",
	AddressLine2: "",
	JobTitle: "Computer Engineer",
	Bio: "Computer Scientist with 3 years of experience in automation, machine learning, and data sceince. Passionate about using AI to create better workflows."
};

const Links = {
	Link1: "https://to-show-i-can.tumblr.com/",
	Link2: "https://www.linkedin.com/in/james-howe-17100b206/",
	Link3: "https://jameshowe.blogs.bucknell.edu/redirect/"
};

const Skills = {
	Python: ["Python(Numpy, Pandas, Tensorflow, Keras)", 90],
	Linux: ["Linux(Debian)", 85],
	Javascript: ["JavaScript", 60],
	Model: ["3D modeling", 40],
	C: ["C++", 40],
	Java: ["Java", 30]
};



//Changes all the Text Values of the spans 
for (const [key, value] of Object.entries(MyInfo)) {
  Array.from(document.getElementsByClassName(key)).forEach(elem => (elem.textContent = value));
}

//For Links
for (const [key, value] of Object.entries(Links)) {
	Array.from(document.getElementsByClassName(key)).forEach(elem => (elem.setAttribute("href", value)));
}

//For Skills 
const SkillDiv = document.getElementById("Skills");
for (const [key, value] of Object.entries(Skills)) {
	const skillWrapper = document.createElement("div");
	skillWrapper.setAttribute("class", "progress mt-4");
	const skill = document.createElement("div");
	const node = document.createTextNode(value[0]);
	skillWrapper.appendChild(skill);
	skill.appendChild(node);
	skill.setAttribute("class", "progress-bar bg-info");
	//bg-success - green
	//bg-warning - yellow
	//bg-danger - red
	skill.setAttribute("role", "progressbar");
	skill.setAttribute("aria-valuenow", value[1]);
	skill.setAttribute("aria-valuemin", "0");
    skill.setAttribute("aria-valuemax", "100");
	skill.setAttribute("style", "width:".concat(value[1]).concat("%"));
	
	SkillDiv.appendChild(skillWrapper);
}

//Change the link on emails 
Array.from(document.getElementsByClassName("Email")).forEach(elem => (elem.setAttribute("href","mailto:".concat(MyInfo["Email"]))));

function test(event){
	$.getJSON('https://api.db-ip.com/v2/free/self', function(data) {
		info = JSON.stringify(data, null, 2)
		console.log(info);
	});
}
Date.now()
// test();
// d94bfac5-11f5-4077-ab82-0ee82f297427
function sendToPantry(){
	// var info = null;
	$.getJSON('https://api.db-ip.com/v2/free/self', function(data) {
		info = JSON.stringify(data, null, 2)
		// console.log(info);
		var date = new Date();
		// console.log(TStamp);
		let x = {};
		x[date.toGMTString()] = data
		// console.log(x);
		let sendData = JSON.stringify(x, null, 2);
		// console.log(sendData);
		const settings = {
			"async": true,
			"crossDomain": true,
			"url": "https://getpantry.cloud/apiv1/pantry/d94bfac5-11f5-4077-ab82-0ee82f297427/basket/newBasket12",
			"method": "PUT",
			"headers": {
			"Content-Type": "application/json"
			},
			"processData": false,
			"data": sendData
		};
		
		$.ajax(settings).done(function (response) {
			// console.log(response);
		});
	});
	

}
sendToPantry()

