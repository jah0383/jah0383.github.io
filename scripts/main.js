const trans = true;
const MyInfo = {
	Name: "John Doe",
	FirstName: ":3",
	LastName: "Howe",
	Age: 22,
	Phone: "(203) 524-4312",
	Email: "jah083@bucknell.edu",
	AddressLine1: "",
	AddressLine2: "",
	JobTitle: "Computer Engineer",
	Bio: "Just a gal having some fun on her computer :3"

};

if(trans){
	MyInfo["Name"] = "Piper Howe"
	MyInfo["FirstName"] = "Piper"
}
else{
	MyInfo["Name"] = "James Howe"
	MyInfo["FirstName"] = "James"
}


for (const [key, value] of Object.entries(MyInfo)) {
  Array.from(document.getElementsByClassName(key)).forEach(elem => (elem.textContent = value));
}


//// Create a button element
//const button = document.createElement('button')
//
//// Set the button text to 'Can you click me?'
//button.innerText = 'Can you click me?'
//
//// Attach the "click" event to your button
//button.addEventListener('click', () => {
//  // When there is a "click"
//  // it shows an alert in the browser
//  alert('Oh')
//  console.log("Test2")
//})
//
//document.body.appendChild(button)