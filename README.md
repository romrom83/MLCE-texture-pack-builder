**Currently doesn't work on the MinecraftConsole fork due to some patches they added, it'll still work on the original source code while I'm working to make this compatible with both**

# MLCE-texture-pack-builder
Simple python script to compile custom texture packs for Minecraft Legacy Console Edition

You have to keep the file structure the same as the example source pack I provided or the game will crash!  
the game should accept x32 textures and more, But the script that generate them will be added in a future commit

just drag the source folder on the script and move what's inside the output in a subfolder of your DLC folder

Example of what the pack should look like at the end:  
https://github.com/ContinuedOak/Legacy-Edition-Resource-Packs  
thanks so much to ContinuedOak for providing this pack!

What could come next:
- Support for the following files: Languages.loc Colours.col Media.arc
- Java to LCE texture pack automatic converter (currently you have to stitch your texture atlas yourself, very time intensive!)
- Skin packs, map packs etc
  
Those files are used to override any text color and UI in the game, that's also why I'd be more inclined to call them ressource packs and not texture packs!

If you dont trust the exe you can compile the .pyw yourself, I removed all dependencies

