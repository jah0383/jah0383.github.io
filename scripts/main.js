
const MyInfo = {
	Name: "James Howe",
	FirstName: "James",
	LastName: "Howe",
	Age: 22,
	Phone: "(203) 524-4312",
	Email: "jah083@bucknell.edu",
	AddressLine1: "",
	AddressLine2: "",
	JobTitle: "Computer Engineer",
	Bio: "Graduating Senior From Bucknell University looking for some work!"
};

const Links = {
	Link1: "https://to-show-i-can.tumblr.com/",
	Link2: "https://www.linkedin.com/in/james-howe-17100b206/",
	Link3: "http://jameshowe.blogs.bucknell.edu/files/2023/04/James-Resume-1.pdf"
};

const Skills = {
	Python: ["Python(Numpy, Pandas, Tensorflow, Keras)", 90],
	Linux: ["Linux", 85],
	Git: ["Git", 80],
	Javascript: ["JavaScript(This website and the gear thing for example)", 60],
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



